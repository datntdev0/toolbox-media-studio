"""Scraping route tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from app.domain.scraping_results import ScrapingResult
from app.domain.scrapings import ScrapingTaskStatus
from app.repositories.scraping_repository import InMemoryScrapingRepository
from app.repositories.scraping_result_repository import InMemoryScrapingResultRepository
from tests.conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD

METADATA_HTML = """
<html>
  <body>
    <img src="/cover.jpg" alt="Test Novel">
    <h1>Test Novel</h1>
    <div>作者： Test Author 分類：Fantasy 更新： 2026-07-23</div>
    <p>Test description</p>
    <h3>Test Novel 全部章节</h3>
    <ul>
      <li><a href="/0603625457/1.html">Chapter 1</a></li>
      <li><a href="/0603625457/2.html">Chapter 2</a></li>
    </ul>
  </body>
</html>
"""


def test_create_requires_auth_and_exact_request_fields(client: TestClient) -> None:
    unauthorized = client.post(
        "/api/scrapings",
        json={
            "crawlerId": "novel543",
            "sourceUrl": "https://www.novel543.com/0603625457/dir",
        },
    )
    token = _login(client)
    invalid = client.post(
        "/api/scrapings",
        headers=_headers(token),
        json={
            "crawlerId": "novel543",
            "sourceUrl": "https://www.novel543.com/0603625457/dir",
            "title": "Untrusted",
        },
    )

    assert unauthorized.status_code == 401
    assert invalid.status_code == 422


def test_create_persists_created_tasks_without_publishing(
    client: TestClient,
    flaresolverr_client: Any,
    scraping_repository: InMemoryScrapingRepository,
    queue_publisher: Any,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    token = _login(client)
    payload = {
        "crawlerId": "novel543",
        "sourceUrl": "https://www.novel543.com/0603625457/dir",
    }

    first = client.post("/api/scrapings", headers=_headers(token), json=payload)
    second = client.post("/api/scrapings", headers=_headers(token), json=payload)

    assert first.status_code == 202
    assert first.headers["location"] == f"/api/scrapings/{first.json()['id']}"
    assert first.json()["reused"] is False
    assert first.json()["progress"] == {
        "total": 2,
        "created": 2,
        "queued": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
    }
    assert "status" not in first.json()
    assert "attempts" not in first.json()
    assert second.status_code == 202
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["reused"] is True
    assert queue_publisher.messages == []

    stored = scraping_repository.get(first.json()["id"], _admin_id(client, token))
    assert stored is not None
    assert [task.title for task in stored.tasks] == ["Chapter 1", "Chapter 2"]
    assert [task.manifest_index for task in stored.tasks] == [0, 1]
    assert all(task.status == ScrapingTaskStatus.CREATED for task in stored.tasks)


def test_list_and_detail_return_summaries_and_embedded_tasks(
    client: TestClient,
    flaresolverr_client: Any,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    token = _login(client)
    created = _create(client, token)

    listed = client.get("/api/scrapings", headers=_headers(token))
    detail = client.get(
        f"/api/scrapings/{created['id']}",
        headers=_headers(token),
    )

    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    assert "tasks" not in listed.json()["items"][0]
    assert detail.status_code == 200
    assert detail.json()["metadata"]["title"] == "Test Novel"
    assert [task["title"] for task in detail.json()["tasks"]] == [
        "Chapter 1",
        "Chapter 2",
    ]
    assert all(task["resultAvailable"] is False for task in detail.json()["tasks"])
    assert "status" not in detail.json()
    assert "lastError" not in detail.json()


def test_duplicate_create_refreshes_metadata_and_appends_new_chapters(
    client: TestClient,
    flaresolverr_client: Any,
    scraping_repository: InMemoryScrapingRepository,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    token = _login(client)
    first = _create(client, token)
    flaresolverr_client.html = METADATA_HTML.replace(
        "</ul>",
        '<li><a href="/0603625457/3.html">Chapter 3</a></li></ul>',
    ).replace("Test Novel</h1>", "Refreshed Novel</h1>")

    second = client.post(
        "/api/scrapings",
        headers=_headers(token),
        json={
            "crawlerId": "novel543",
            "sourceUrl": "https://www.novel543.com/0603625457/dir",
        },
    )

    assert second.status_code == 202
    assert second.json()["id"] == first["id"]
    assert second.json()["reused"] is True
    stored = scraping_repository.get(first["id"], _admin_id(client, token))
    assert stored is not None
    assert stored.metadata.title == "Refreshed Novel"
    assert [task.chapter_number for task in stored.tasks] == [1, 2, 3]
    assert stored.tasks[2].status == ScrapingTaskStatus.CREATED


def test_start_and_stop_manage_task_queue_messages(
    client: TestClient,
    flaresolverr_client: Any,
    scraping_repository: InMemoryScrapingRepository,
    queue_publisher: Any,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    token = _login(client)
    created = _create(client, token)

    started = client.patch(
        f"/api/scrapings/{created['id']}/start",
        headers=_headers(token),
        json={
            "chapterFrom": 1,
            "chapterTo": 2,
            "refetch": True,
        },
    )

    assert started.status_code == 202
    assert started.json()["progress"]["queued"] == 2
    assert len(queue_publisher.messages) == 2
    assert {message[1]["taskId"] for message in queue_publisher.messages} == {
        task["id"] for task in started.json()["tasks"]
    }
    assert all(message[1]["refetch"] is True for message in queue_publisher.messages)

    repeated = client.patch(
        f"/api/scrapings/{created['id']}/start",
        headers=_headers(token),
        json={"chapterFrom": 1, "chapterTo": 2},
    )
    assert repeated.status_code == 202
    assert len(queue_publisher.messages) == 2

    forced = client.patch(
        f"/api/scrapings/{created['id']}/start",
        headers=_headers(token),
        json={"chapterFrom": 1, "chapterTo": 2, "force": True},
    )
    assert forced.status_code == 202
    assert len(queue_publisher.messages) == 4

    stopped = client.patch(
        f"/api/scrapings/{created['id']}/stop",
        headers=_headers(token),
    )
    assert stopped.status_code == 200
    assert stopped.json()["progress"]["created"] == 2
    assert stopped.json()["progress"]["queued"] == 0
    stored = scraping_repository.get(created["id"], _admin_id(client, token))
    assert stored is not None
    assert all(task.status == ScrapingTaskStatus.CREATED for task in stored.tasks)


def test_start_validates_range_and_openapi_has_task_scoped_contract(
    client: TestClient,
    flaresolverr_client: Any,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    token = _login(client)
    created = _create(client, token)

    reversed_range = client.patch(
        f"/api/scrapings/{created['id']}/start",
        headers=_headers(token),
        json={"chapterFrom": 2, "chapterTo": 1},
    )
    missing_range = client.patch(
        f"/api/scrapings/{created['id']}/start",
        headers=_headers(token),
        json={"chapterFrom": 99, "chapterTo": 100},
    )
    openapi = client.get("/openapi.json").json()

    assert reversed_range.status_code == 422
    assert missing_range.status_code == 422
    parameters = openapi["paths"]["/api/scrapings"]["get"]["parameters"]
    assert "status" not in {parameter["name"] for parameter in parameters}
    summary_schema = openapi["components"]["schemas"]["ScrapingSummaryResponse"]
    assert "status" not in summary_schema["properties"]
    assert "/api/scrapings/{id}/start" in openapi["paths"]
    assert "/api/scrapings/{id}/stop" in openapi["paths"]


def test_start_publication_failure_leaves_tasks_queued_for_force_retry(
    client: TestClient,
    flaresolverr_client: Any,
    scraping_repository: InMemoryScrapingRepository,
    queue_publisher: Any,
    monkeypatch: Any,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    token = _login(client)
    created = _create(client, token)
    published = 0

    def fail_second_message(queue_name: str, message: Any) -> None:
        nonlocal published
        del queue_name, message
        published += 1
        if published == 2:
            raise RuntimeError("queue unavailable")

    monkeypatch.setattr(queue_publisher, "publish", fail_second_message)
    response = client.patch(
        f"/api/scrapings/{created['id']}/start",
        headers=_headers(token),
        json={"chapterFrom": 1, "chapterTo": 2},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Some scraping tasks could not be queued; retry with force"
    )
    stored = scraping_repository.get(created["id"], _admin_id(client, token))
    assert stored is not None
    assert stored.progress.queued == 2


def test_result_endpoint_reads_one_completed_task_result(
    client: TestClient,
    flaresolverr_client: Any,
    scraping_repository: InMemoryScrapingRepository,
    scraping_result_repository: InMemoryScrapingResultRepository,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    token = _login(client)
    created = _create(client, token)
    owner_id = _admin_id(client, token)
    scraping = scraping_repository.get(created["id"], owner_id)
    assert scraping is not None
    task = scraping.tasks[0]

    unavailable = client.get(
        f"/api/scrapings/{scraping.id}/results/{task.id}",
        headers=_headers(token),
    )
    assert unavailable.status_code == 409

    now = datetime.now(UTC)
    scraping_result_repository.upsert(
        ScrapingResult(
            id=task.id,
            scraping_id=scraping.id,
            task_id=task.id,
            title=task.title,
            chapter_number=task.chapter_number,
            content=["First", "Second"],
            created_at=now,
            updated_at=now,
        )
    )
    scraping_repository.update_task(
        scraping.id,
        owner_id,
        task.id,
        ScrapingTaskStatus.COMPLETED,
        attempts=1,
        error=None,
        result_available=True,
        completed_at=now,
        etag=scraping.etag,
    )

    response = client.get(
        f"/api/scrapings/{scraping.id}/results/{task.id}",
        headers=_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["scrapingId"] == scraping.id
    assert response.json()["taskId"] == task.id
    assert response.json()["content"] == ["First", "Second"]


def test_openapi_uses_scraping_result_task_id_path_parameter(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"][
        "/api/scrapings/{id}/results/{taskId}"
    ]["get"]

    assert {
        (parameter["name"], parameter["in"])
        for parameter in operation["parameters"]
    } >= {("id", "path"), ("taskId", "path")}


def test_delete_scraping_removes_owned_resource(
    client: TestClient,
    flaresolverr_client: Any,
    scraping_repository: InMemoryScrapingRepository,
    scraping_result_repository: InMemoryScrapingResultRepository,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    token = _login(client)
    created = _create(client, token)
    scraping = scraping_repository.get(created["id"], _admin_id(client, token))
    assert scraping is not None
    task = scraping.tasks[0]
    now = datetime.now(UTC)
    scraping_result_repository.upsert(
        ScrapingResult(
            id=task.id,
            scraping_id=scraping.id,
            task_id=task.id,
            title=task.title,
            chapter_number=task.chapter_number,
            content=["result"],
            created_at=now,
            updated_at=now,
        )
    )

    unauthorized = client.delete(f"/api/scrapings/{created['id']}")
    deleted = client.delete(
        f"/api/scrapings/{created['id']}",
        headers=_headers(token),
    )
    missing = client.get(
        f"/api/scrapings/{created['id']}",
        headers=_headers(token),
    )
    deleted_again = client.delete(
        f"/api/scrapings/{created['id']}",
        headers=_headers(token),
    )

    assert unauthorized.status_code == 401
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert scraping_result_repository.get(scraping.id, task.id) is None
    assert missing.status_code == 404
    assert deleted_again.status_code == 404


def test_scraping_endpoints_are_not_owner_scoped(
    client: TestClient,
    flaresolverr_client: Any,
    scraping_repository: InMemoryScrapingRepository,
    scraping_result_repository: InMemoryScrapingResultRepository,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    admin_token = _login(client)
    created = _create(client, admin_token)
    scraping = scraping_repository.get(created["id"], _admin_id(client, admin_token))
    assert scraping is not None
    task = scraping.tasks[0]
    now = datetime.now(UTC)
    scraping_result_repository.upsert(
        ScrapingResult(
            id=task.id,
            scraping_id=scraping.id,
            task_id=task.id,
            title=task.title,
            chapter_number=task.chapter_number,
            content=["result"],
            created_at=now,
            updated_at=now,
        )
    )
    scraping_repository.update_task(
        scraping.id,
        scraping.created_by,
        task.id,
        ScrapingTaskStatus.COMPLETED,
        attempts=1,
        error=None,
        result_available=True,
        completed_at=now,
        etag=scraping.etag,
    )
    member = client.post(
        "/api/users",
        headers=_headers(admin_token),
        json={
            "email": "member@example.com",
            "password": "member-password",
            "displayName": "Member User",
        },
    )
    assert member.status_code == 201
    member_token = _login(
        client,
        email="member@example.com",
        password="member-password",
    )

    listed = client.get("/api/scrapings", headers=_headers(member_token))
    detail = client.get(
        f"/api/scrapings/{created['id']}",
        headers=_headers(member_token),
    )
    result = client.get(
        f"/api/scrapings/{created['id']}/results/{task.id}",
        headers=_headers(member_token),
    )
    deleted = client.delete(
        f"/api/scrapings/{created['id']}",
        headers=_headers(member_token),
    )

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [created["id"]]
    assert detail.status_code == 200
    assert result.status_code == 200
    assert result.json()["content"] == ["result"]
    assert deleted.status_code == 204
    assert scraping_result_repository.get(scraping.id, task.id) is None
    assert client.get(
        f"/api/scrapings/{created['id']}",
        headers=_headers(admin_token),
    ).status_code == 404


def test_delete_scraping_keeps_parent_when_result_cleanup_fails(
    client: TestClient,
    flaresolverr_client: Any,
    scraping_repository: InMemoryScrapingRepository,
    scraping_result_repository: InMemoryScrapingResultRepository,
    monkeypatch: Any,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    token = _login(client)
    created = _create(client, token)
    owner_id = _admin_id(client, token)

    def fail_cleanup(scraping_id: str) -> None:
        del scraping_id
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(
        scraping_result_repository,
        "delete_by_scraping",
        fail_cleanup,
    )

    response = client.delete(
        f"/api/scrapings/{created['id']}",
        headers=_headers(token),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Scraping results could not be deleted"
    assert scraping_repository.get(created["id"], owner_id) is not None


def _create(client: TestClient, token: str) -> dict[str, Any]:
    response = client.post(
        "/api/scrapings",
        headers=_headers(token),
        json={
            "crawlerId": "novel543",
            "sourceUrl": "https://www.novel543.com/0603625457/dir",
        },
    )
    assert response.status_code == 202
    return response.json()


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


def _admin_id(client: TestClient, token: str) -> str:
    response = client.get("/auth/me", headers=_headers(token))
    assert response.status_code == 200
    return response.json()["id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
