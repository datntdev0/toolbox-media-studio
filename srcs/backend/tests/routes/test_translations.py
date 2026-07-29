"""Translation-management endpoint tests."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.domain.novels import NovelChapter
from app.domain.translation_results import TranslationResult
from app.domain.translations import TranslationProgress, TranslationTaskStatus
from app.repositories.novel_chapter_repository import InMemoryNovelChapterRepository
from app.repositories.translation_repository import InMemoryTranslationRepository
from app.repositories.translation_result_repository import (
    InMemoryTranslationResultRepository,
)
from tests.conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD


def _login(
    client: TestClient,
    email: str = TEST_ADMIN_EMAIL,
    password: str = TEST_ADMIN_PASSWORD,
) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_novel(client: TestClient, headers: dict[str, str], title: str) -> dict[str, Any]:
    response = client.post(
        "/api/novels",
        headers=headers,
        json={"title": title, "language": "zh"},
    )
    assert response.status_code == 201
    return response.json()


def _create_translation(
    client: TestClient,
    headers: dict[str, str],
    novel_id: str,
    *,
    name: str = "Vietnamese translation",
    target_language: str = "vi",
) -> dict[str, Any]:
    response = client.post(
        "/api/translations",
        headers=headers,
        json={
            "name": name,
            "novelId": novel_id,
            "targetLanguage": target_language,
        },
    )
    assert response.status_code == 201
    return response.json()


def _chapter(
    novel_id: str,
    id: str,
    manifest_index: int,
    *,
    content: list[str] | None = None,
) -> NovelChapter:
    now = datetime.now(UTC)
    return NovelChapter(
        id=id,
        novel_id=novel_id,
        scraping_task_id=id,
        title=f"Chapter {manifest_index + 1}",
        chapter_number=manifest_index + 1,
        manifest_index=manifest_index,
        source_url=f"https://example.test/{id}",
        content=list(content or [f"Source {id}"]),
        content_available=True,
        manually_edited=False,
        source_updated=False,
        source_removed=False,
        source_result_updated_at=now,
        created_at=now,
        updated_at=now,
    )


def test_translation_crud_persists_configuration_and_allows_duplicates(
    client: TestClient,
) -> None:
    headers = _headers(_login(client))
    first_novel = _create_novel(client, headers, "First Novel")
    second_novel = _create_novel(client, headers, "Second Novel")

    first = _create_translation(client, headers, first_novel["id"])
    duplicate = _create_translation(client, headers, first_novel["id"])
    assert first["id"] != duplicate["id"]
    assert first["novel"]["title"] == "First Novel"
    assert first["status"] == "needs_setup"
    assert first["configuration"] is None
    assert "kind" not in first

    updated = client.put(
        f"/api/translations/{first['id']}",
        headers=headers,
        json={
            "name": "English edition",
            "novelId": second_novel["id"],
            "targetLanguage": "en",
            "configuration": {
                "providerId": "openai",
                "modelId": "gpt-5-mini",
                "globalPrompt": "Translate this literary chapter faithfully.",
            },
            "etag": first["etag"],
        },
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["name"] == "English edition"
    assert updated_body["novelId"] == second_novel["id"]
    assert updated_body["targetLanguage"] == "en"
    assert updated_body["novel"]["title"] == "Second Novel"
    assert updated_body["status"] == "ready"
    assert updated_body["configuration"] == {
        "providerId": "openai",
        "modelId": "gpt-5-mini",
        "globalPrompt": "Translate this literary chapter faithfully.",
    }

    fetched = client.get(f"/api/translations/{first['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["configuration"] == updated_body["configuration"]

    listed = client.get("/api/translations", headers=headers)
    assert listed.status_code == 200
    listed_item = next(item for item in listed.json()["items"] if item["id"] == first["id"])
    assert listed_item["configuration"] == updated_body["configuration"]

    assert client.delete(f"/api/translations/{first['id']}", headers=headers).status_code == 204
    assert (
        client.get(f"/api/translations/{first['id']}", headers=headers).status_code == 404
    )


def test_translation_operations_are_not_restricted_to_creator(client: TestClient) -> None:
    admin_headers = _headers(_login(client))
    novel = _create_novel(client, admin_headers, "Shared Novel")
    translation = _create_translation(
        client,
        admin_headers,
        novel["id"],
        name="Shared translation",
    )

    created_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "email": "translation-member@example.com",
            "password": "member-password",
            "displayName": "Translation Member",
        },
    )
    assert created_user.status_code == 201
    member_headers = _headers(
        _login(client, "translation-member@example.com", "member-password")
    )

    listed = client.get("/api/translations", headers=member_headers)
    assert listed.status_code == 200
    assert any(item["id"] == translation["id"] for item in listed.json()["items"])

    updated = client.put(
        f"/api/translations/{translation['id']}",
        headers=member_headers,
        json={
            "name": "Updated by member",
            "novelId": novel["id"],
            "targetLanguage": "ja",
            "configuration": None,
            "etag": translation["etag"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated by member"
    assert updated.json()["targetLanguage"] == "ja"
    assert (
        client.delete(
            f"/api/translations/{translation['id']}",
            headers=member_headers,
        ).status_code
        == 204
    )


def test_translation_returns_null_for_deleted_bound_novel(client: TestClient) -> None:
    headers = _headers(_login(client))
    novel = _create_novel(client, headers, "Temporary Novel")
    translation = _create_translation(client, headers, novel["id"])

    assert client.delete(f"/api/novels/{novel['id']}", headers=headers).status_code == 204
    response = client.get(f"/api/translations/{translation['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["novel"] is None


def test_translation_update_with_stale_etag_returns_412(client: TestClient) -> None:
    headers = _headers(_login(client))
    novel = _create_novel(client, headers, "Concurrency Novel")
    translation = _create_translation(client, headers, novel["id"])
    payload = {
        "name": "Updated once",
        "novelId": novel["id"],
        "targetLanguage": "en",
        "configuration": None,
        "etag": translation["etag"],
    }
    assert client.put(
        f"/api/translations/{translation['id']}",
        headers=headers,
        json=payload,
    ).status_code == 200
    stale = client.put(
        f"/api/translations/{translation['id']}",
        headers=headers,
        json={**payload, "name": "Updated twice"},
    )
    assert stale.status_code == 412


def test_translation_validation_missing_novel_and_legacy_routes(client: TestClient) -> None:
    headers = _headers(_login(client))
    missing_novel = client.post(
        "/api/translations",
        headers=headers,
        json={
            "name": "Missing novel",
            "novelId": "missing",
            "targetLanguage": "vi",
        },
    )
    assert missing_novel.status_code == 404
    invalid_token = client.get(
        "/api/translations?continuationToken=invalid",
        headers=headers,
    )
    assert invalid_token.status_code == 422
    assert client.get("/api/translations?continuationToken=-1", headers=headers).status_code == 422
    assert client.get("/api/workspaces", headers=headers).status_code == 404
    legacy_body = client.post(
        "/api/translations",
        headers=headers,
        json={
            "name": "Legacy body",
            "kind": "translation",
            "novelId": "missing",
            "targetLanguage": "vi",
        },
    )
    assert legacy_body.status_code == 422

    openapi = client.get("/openapi.json").json()
    assert all("Workspace" not in schema for schema in openapi["components"]["schemas"])


def test_translation_configuration_rejects_blank_values(client: TestClient) -> None:
    headers = _headers(_login(client))
    novel = _create_novel(client, headers, "Validation Novel")
    translation = _create_translation(client, headers, novel["id"])

    response = client.put(
        f"/api/translations/{translation['id']}",
        headers=headers,
        json={
            "name": translation["name"],
            "novelId": novel["id"],
            "targetLanguage": translation["targetLanguage"],
            "configuration": {
                "providerId": " ",
                "modelId": "gpt-5-mini",
                "globalPrompt": "Translate.",
            },
            "etag": translation["etag"],
        },
    )
    assert response.status_code == 422


def test_translation_start_stop_and_result_workflow(
    client: TestClient,
    novel_chapter_repository: InMemoryNovelChapterRepository,
    translation_repository: InMemoryTranslationRepository,
    translation_result_repository: InMemoryTranslationResultRepository,
    queue_publisher: Any,
) -> None:
    headers = _headers(_login(client))
    novel = _create_novel(client, headers, "Task Novel")
    for index in range(2):
        novel_chapter_repository.save(_chapter(novel["id"], f"chapter-{index + 1}", index))
    translation = _create_translation(client, headers, novel["id"])

    detail = client.get(f"/api/translations/{translation['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["progress"]["created"] == 2
    assert [task["id"] for task in detail.json()["tasks"]] == [
        "chapter-1",
        "chapter-2",
    ]
    unconfigured = client.patch(
        f"/api/translations/{translation['id']}/start",
        headers=headers,
        json={"chapterIndexFrom": 1, "chapterIndexTo": 2},
    )
    assert unconfigured.status_code == 409

    configured = client.put(
        f"/api/translations/{translation['id']}",
        headers=headers,
        json={
            "name": translation["name"],
            "novelId": novel["id"],
            "targetLanguage": translation["targetLanguage"],
            "configuration": {
                "providerId": "mock",
                "modelId": "copy",
                "globalPrompt": "Copy.",
            },
            "etag": translation["etag"],
        },
    ).json()
    started = client.patch(
        f"/api/translations/{translation['id']}/start",
        headers=headers,
        json={
            "chapterIndexFrom": 1,
            "chapterIndexTo": 2,
            "refetch": True,
        },
    )
    assert started.status_code == 202
    assert started.json()["novel"]["id"] == novel["id"]
    assert started.json()["progress"]["queued"] == 2
    assert [message[0] for message in queue_publisher.messages] == [
        "translations",
        "translations",
    ]
    assert all(message[1]["refetch"] is True for message in queue_publisher.messages)

    repeated = client.patch(
        f"/api/translations/{translation['id']}/start",
        headers=headers,
        json={"chapterIndexFrom": 1, "chapterIndexTo": 2},
    )
    assert repeated.status_code == 202
    assert len(queue_publisher.messages) == 2
    stopped = client.patch(
        f"/api/translations/{translation['id']}/stop",
        headers=headers,
    )
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    assert stopped.json()["progress"]["created"] == 2

    stored = translation_repository.get_by_id(configured["id"])
    assert stored is not None
    stored.tasks[0].status = TranslationTaskStatus.COMPLETED
    stored.tasks[0].result_available = True
    stored.progress = TranslationProgress.from_tasks(stored.tasks)
    translation_repository.update(stored, stored.etag)
    now = datetime.now(UTC)
    translation_result_repository.upsert(
        TranslationResult(
            id="chapter-1",
            translation_id=stored.id,
            task_id="chapter-1",
            title="Chapter 1",
            chapter_number=1,
            content=["Copied source"],
            created_at=now,
            updated_at=now,
        )
    )
    result = client.get(
        f"/api/translations/{stored.id}/result/chapter-1",
        headers=headers,
    )
    assert result.status_code == 200
    assert result.json()["taskId"] == "chapter-1"
    assert result.json()["content"] == ["Copied source"]


def test_translation_sync_preserves_results_and_marks_removed_sources(
    client: TestClient,
    novel_chapter_repository: InMemoryNovelChapterRepository,
    translation_repository: InMemoryTranslationRepository,
) -> None:
    headers = _headers(_login(client))
    novel = _create_novel(client, headers, "Sync Novel")
    changed = novel_chapter_repository.save(_chapter(novel["id"], "changed", 0))
    removed = novel_chapter_repository.save(_chapter(novel["id"], "removed", 1))
    novel_chapter_repository.save(_chapter(novel["id"], "stable", 2))
    translation = _create_translation(client, headers, novel["id"])

    stored = translation_repository.get_by_id(translation["id"])
    assert stored is not None
    changed_task = next(task for task in stored.tasks if task.id == "changed")
    changed_task.status = TranslationTaskStatus.COMPLETED
    changed_task.result_available = True
    stored.progress = TranslationProgress.from_tasks(stored.tasks)
    translation_repository.update(stored, stored.etag)

    changed.title = "Changed title"
    changed.updated_at = datetime.now(UTC) + timedelta(minutes=1)
    novel_chapter_repository.save(changed, etag=changed.etag)
    removed.source_removed = True
    removed.updated_at = datetime.now(UTC) + timedelta(minutes=1)
    novel_chapter_repository.save(removed, etag=removed.etag)
    novel_chapter_repository.save(_chapter(novel["id"], "added", 3))

    synced = client.patch(
        f"/api/translations/{translation['id']}/sync",
        headers=headers,
    )
    assert synced.status_code == 200
    assert synced.json()["changes"] == {
        "added": 1,
        "refreshed": 0,
        "preserved": 1,
        "removed": 1,
    }
    tasks = {task["id"]: task for task in synced.json()["translation"]["tasks"]}
    assert tasks["changed"]["sourceUpdated"] is True
    assert tasks["removed"]["sourceRemoved"] is True
    assert tasks["changed"]["resultAvailable"] is True
