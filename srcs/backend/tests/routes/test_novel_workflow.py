"""Novel binding, synchronization, and chapter route tests."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.domain.scraping_results import ScrapingResult
from app.domain.scrapings import (
    Scraping,
    ScrapingMetadata,
    ScrapingProgress,
    ScrapingTask,
    ScrapingTaskStatus,
)
from app.repositories.scraping_repository import InMemoryScrapingRepository
from app.repositories.scraping_result_repository import InMemoryScrapingResultRepository
from tests.conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD


def test_bind_and_chapter_routes_allow_an_authenticated_non_owner(
    client: TestClient,
    scraping_repository: InMemoryScrapingRepository,
    scraping_result_repository: InMemoryScrapingResultRepository,
) -> None:
    admin_token = _login(client)
    admin_headers = _headers(admin_token)
    novel = client.post(
        "/api/novels",
        headers=admin_headers,
        json={"title": "Owner novel"},
    ).json()
    scraping = _seed_scraping(
        scraping_repository,
        tasks=[
            _task("chapter-2", 1, result_available=False),
            _task("chapter-1", 0, result_available=True),
        ],
    )
    scraping_result_repository.upsert(
        _result(scraping.id, "chapter-1", ["First paragraph", "Second paragraph"])
    )
    member_token = _create_member_and_login(client, admin_token)
    member_headers = _headers(member_token)

    unauthorized = client.patch(
        f"/api/novels/{novel['id']}/bind",
        json={"scrapingId": scraping.id},
    )
    bound = client.patch(
        f"/api/novels/{novel['id']}/bind",
        headers=member_headers,
        json={"scrapingId": scraping.id},
    )

    assert unauthorized.status_code == 401
    assert bound.status_code == 200
    body = bound.json()
    assert body["changes"] == {
        "added": 2,
        "refreshed": 0,
        "preserved": 0,
        "removed": 0,
    }
    assert body["novel"]["binding"]["scrapingId"] == scraping.id
    assert set(body["novel"]["binding"]) == {
        "scrapingId",
        "boundAt",
        "lastSyncedAt",
    }
    assert body["novel"]["chapterCount"] == 2
    assert [chapter["id"] for chapter in body["novel"]["chapters"]] == [
        "chapter-1",
        "chapter-2",
    ]
    assert body["novel"]["chapters"][0]["contentAvailable"] is True
    assert body["novel"]["chapters"][1]["contentAvailable"] is False

    # Existing CRUD detail remains owner-scoped while new workflow routes are global.
    assert client.get(
        f"/api/novels/{novel['id']}",
        headers=member_headers,
    ).status_code == 404
    chapter = client.get(
        f"/api/novels/{novel['id']}/chapters/chapter-1",
        headers=member_headers,
    )
    assert chapter.status_code == 200
    assert chapter.json()["content"] == ["First paragraph", "Second paragraph"]

    edited = client.put(
        f"/api/novels/{novel['id']}/chapters/chapter-1",
        headers=member_headers,
        json={
            "content": "Locally edited line\ncontinued\n\nSecond paragraph",
            "etag": chapter.json()["etag"],
        },
    )
    assert edited.status_code == 200
    assert edited.json()["content"] == [
        "Locally edited line\ncontinued",
        "Second paragraph",
    ]
    assert edited.json()["manuallyEdited"] is True

    stale = client.put(
        f"/api/novels/{novel['id']}/chapters/chapter-1",
        headers=admin_headers,
        json={"content": "Stale", "etag": chapter.json()["etag"]},
    )
    assert stale.status_code == 412


def test_bind_and_sync_conflicts_have_stable_status_codes(
    client: TestClient,
    scraping_repository: InMemoryScrapingRepository,
) -> None:
    token = _login(client)
    headers = _headers(token)
    scraping = _seed_scraping(
        scraping_repository,
        tasks=[_task("chapter-1", 0)],
    )
    novel = client.post(
        "/api/novels",
        headers=headers,
        json={"title": "Conflict novel"},
    ).json()
    unbound = client.post(
        "/api/novels",
        headers=headers,
        json={"title": "Unbound novel"},
    ).json()

    first = client.patch(
        f"/api/novels/{novel['id']}/bind",
        headers=headers,
        json={"scrapingId": scraping.id},
    )
    repeated = client.patch(
        f"/api/novels/{novel['id']}/bind",
        headers=headers,
        json={"scrapingId": scraping.id},
    )
    unbound_sync = client.patch(
        f"/api/novels/{unbound['id']}/sync",
        headers=headers,
    )
    synced = client.patch(
        f"/api/novels/{novel['id']}/sync",
        headers=headers,
    )

    assert first.status_code == 200
    assert repeated.status_code == 409
    assert unbound_sync.status_code == 409
    assert synced.status_code == 200
    assert synced.json()["changes"] == {
        "added": 0,
        "refreshed": 0,
        "preserved": 0,
        "removed": 0,
    }


def test_novel_workflow_openapi_uses_json_contracts_and_chapter_id_alias(
    client: TestClient,
) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert paths["/api/novels/{id}/bind"]["patch"]["operationId"] == "bind_novel"
    assert paths["/api/novels/{id}/sync"]["patch"]["operationId"] == "sync_novel"
    chapter_path = paths["/api/novels/{id}/chapters/{chapterId}"]
    assert chapter_path["get"]["operationId"] == "get_novel_chapter"
    assert chapter_path["put"]["operationId"] == "update_novel_chapter"
    assert {
        (parameter["name"], parameter["in"])
        for parameter in chapter_path["put"]["parameters"]
    } >= {("id", "path"), ("chapterId", "path")}

    bind_schema = schema["components"]["schemas"]["NovelBindRequest"]
    assert bind_schema["required"] == ["scrapingId"]
    assert set(bind_schema["properties"]) == {"scrapingId"}
    binding_schema = schema["components"]["schemas"]["NovelBindingResponse"]
    assert set(binding_schema["required"]) == {
        "scrapingId",
        "boundAt",
        "lastSyncedAt",
    }
    assert set(binding_schema["properties"]) == {
        "scrapingId",
        "boundAt",
        "lastSyncedAt",
    }
    edit_schema = schema["components"]["schemas"]["NovelChapterUpdateRequest"]
    assert set(edit_schema["required"]) == {"content", "etag"}
    assert set(edit_schema["properties"]) == {"content", "etag"}


def _seed_scraping(
    repository: InMemoryScrapingRepository,
    *,
    tasks: list[ScrapingTask],
) -> Scraping:
    now = datetime.now(UTC)
    scraping = Scraping(
        id="scraping-workflow",
        crawler_id="novel543",
        source_url="https://example.test/source",
        metadata=ScrapingMetadata(
            source_novel_id="source",
            title="Scraping owned by someone else",
            author=None,
            category=None,
            updated_date=None,
            protagonists=[],
            description=None,
            cover_image_url=None,
            fetched_at=now,
        ),
        tasks=tasks,
        progress=ScrapingProgress.from_tasks(tasks),
        idempotency_key="workflow-key",
        created_by="unrelated-owner",
        created_at=now,
        updated_at=now,
    )
    return repository.create_or_merge(scraping).scraping


def _task(
    task_id: str,
    manifest_index: int,
    *,
    result_available: bool = False,
) -> ScrapingTask:
    return ScrapingTask(
        id=task_id,
        source_url=f"https://example.test/{task_id}",
        title=f"Chapter {manifest_index + 1}",
        chapter_number=manifest_index + 1,
        manifest_index=manifest_index,
        status=(
            ScrapingTaskStatus.COMPLETED
            if result_available
            else ScrapingTaskStatus.CREATED
        ),
        result_available=result_available,
    )


def _result(
    scraping_id: str,
    task_id: str,
    content: list[str],
) -> ScrapingResult:
    now = datetime.now(UTC)
    return ScrapingResult(
        id=task_id,
        scraping_id=scraping_id,
        task_id=task_id,
        title=task_id,
        chapter_number=1,
        content=content,
        created_at=now,
        updated_at=now,
    )


def _create_member_and_login(client: TestClient, admin_token: str) -> str:
    created = client.post(
        "/api/users",
        headers=_headers(admin_token),
        json={
            "email": "workflow-member@example.com",
            "password": "member-password",
            "displayName": "Workflow member",
        },
    )
    assert created.status_code == 201
    return _login(
        client,
        email="workflow-member@example.com",
        password="member-password",
    )


def _login(
    client: TestClient,
    email: str = TEST_ADMIN_EMAIL,
    password: str = TEST_ADMIN_PASSWORD,
) -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
