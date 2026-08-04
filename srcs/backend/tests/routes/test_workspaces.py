"""Audio workspace and novel-language endpoint tests."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.domain.novels import NovelChapter
from app.domain.translation_results import TranslationResult
from app.domain.translations import (
    TranslationProgress,
    TranslationTask,
    TranslationTaskStatus,
)
from app.domain.workspace_results import WorkspaceResult
from app.domain.workspaces import WorkspaceProgress, WorkspaceTaskStatus
from app.repositories.novel_chapter_repository import InMemoryNovelChapterRepository
from app.repositories.translation_repository import InMemoryTranslationRepository
from app.repositories.translation_result_repository import (
    InMemoryTranslationResultRepository,
)
from app.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.repositories.workspace_result_repository import InMemoryWorkspaceResultRepository
from tests.conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, FakeQueuePublisher


def test_workspace_crud_and_language_aware_chapter_reads(
    client: TestClient,
    novel_chapter_repository: InMemoryNovelChapterRepository,
    translation_repository: InMemoryTranslationRepository,
    translation_result_repository: InMemoryTranslationResultRepository,
) -> None:
    admin_token = _login(client)
    headers = _headers(admin_token)
    novel = client.post(
        "/api/novels",
        headers=headers,
        json={"title": "Audio source novel", "language": "zh"},
    ).json()
    novel_chapter_repository.save(_chapter(novel["id"], "chapter-1", 0))
    novel_chapter_repository.save(_chapter(novel["id"], "chapter-2", 1))

    older = _create_translation(client, headers, novel["id"], "Older")
    _complete_translation(
        translation_repository,
        translation_result_repository,
        older["id"],
        "chapter-1",
        "Older translated title",
        "Older translated line",
        updated_at=datetime.now(UTC),
    )
    newer = _create_translation(client, headers, novel["id"], "Newer")
    _complete_translation(
        translation_repository,
        translation_result_repository,
        newer["id"],
        "chapter-1",
        "Newest translated title",
        "Newest translated line",
        updated_at=datetime.now(UTC) + timedelta(minutes=1),
    )

    languages = client.get(
        f"/api/novels/{novel['id']}/languages",
        headers=headers,
    )
    assert languages.status_code == 200
    assert languages.json() == {
        "items": [
            {"code": "zh", "sourceType": "original"},
            {"code": "vi", "sourceType": "translation"},
        ]
    }

    original = client.get(
        f"/api/novels/{novel['id']}/chapters/chapter-1",
        headers=headers,
    )
    translated = client.get(
        f"/api/novels/{novel['id']}/chapters/chapter-1?language=vi",
        headers=headers,
    )
    assert original.status_code == 200
    assert original.json()["content"] == ["Original line 1", "Original line 2"]
    assert translated.status_code == 200
    assert translated.json()["content"] == ["Newest translated line"]
    assert translated.json()["title"] == "Newest translated title"

    created = client.post(
        "/api/workspaces",
        headers=headers,
        json={
            "title": "Vietnamese audio",
            "type": "audio",
            "novelId": novel["id"],
            "language": "vi",
        },
    )
    assert created.status_code == 201
    workspace = created.json()
    assert workspace["sourceType"] == "translation"
    assert workspace["sourceAvailable"] is True
    assert "status" not in workspace

    detail = client.get(f"/api/workspaces/{workspace['id']}", headers=headers)
    assert detail.status_code == 200
    chapters = detail.json()["chapters"]
    assert chapters[0]["title"] == "Newest translated title"
    assert chapters[0]["contentAvailable"] is True
    assert chapters[1]["title"] == "Original chapter 2"
    assert chapters[1]["contentAvailable"] is False
    assert client.get(
        f"/api/novels/{novel['id']}/chapters/chapter-2?language=vi",
        headers=headers,
    ).status_code == 404

    updated = client.put(
        f"/api/workspaces/{workspace['id']}",
        headers=headers,
        json={"title": "Updated audio title"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated audio title"
    assert client.put(
        f"/api/workspaces/{workspace['id']}",
        headers=headers,
        json={"title": "Invalid", "language": "zh"},
    ).status_code == 422

    member_headers = _headers(_create_member_and_login(client, admin_token))
    listed = client.get("/api/workspaces?type=audio", headers=member_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [workspace["id"]]
    assert client.get(
        f"/api/workspaces/{workspace['id']}",
        headers=member_headers,
    ).status_code == 200
    member_updated = client.put(
        f"/api/workspaces/{workspace['id']}",
        headers=member_headers,
        json={"title": "Updated by member"},
    )
    assert member_updated.status_code == 200
    assert member_updated.json()["title"] == "Updated by member"

    assert client.delete(
        f"/api/workspaces/{workspace['id']}",
        headers=member_headers,
    ).status_code == 204
    assert client.get(
        f"/api/workspaces/{workspace['id']}",
        headers=headers,
    ).status_code == 404


def test_original_sentinel_and_unknown_language(client: TestClient) -> None:
    headers = _headers(_login(client))
    novel = client.post(
        "/api/novels",
        headers=headers,
        json={"title": "Language-less original"},
    ).json()

    languages = client.get(
        f"/api/novels/{novel['id']}/languages",
        headers=headers,
    )
    assert languages.json() == {
        "items": [{"code": "original", "sourceType": "original"}]
    }
    created = client.post(
        "/api/workspaces",
        headers=headers,
        json={
            "title": "Original audio",
            "type": "audio",
            "novelId": novel["id"],
            "language": "original",
        },
    )
    assert created.status_code == 201
    assert client.post(
        "/api/workspaces",
        headers=headers,
        json={
            "title": "Unknown source",
            "type": "audio",
            "novelId": novel["id"],
            "language": "fr",
        },
    ).status_code == 404
    assert client.post(
        "/api/workspaces",
        headers=headers,
        json={
            "title": "Invalid status",
            "type": "audio",
            "novelId": novel["id"],
            "language": "original",
        },
    ).status_code == 422
    assert client.delete(f"/api/novels/{novel['id']}", headers=headers).status_code == 204
    assert client.get(
        f"/api/workspaces/{created.json()['id']}",
        headers=headers,
    ).status_code == 404


def test_workspace_routes_require_authentication(client: TestClient) -> None:
    assert client.get("/api/workspaces").status_code == 401
    assert client.post(
        "/api/workspaces",
        json={
            "title": "Unauthenticated",
            "type": "audio",
            "novelId": "novel-id",
            "language": "en",
        },
    ).status_code == 401
    assert client.get("/api/novels/novel-id/languages").status_code == 401

    headers = _headers(_login(client))
    assert client.get("/api/workspaces/missing", headers=headers).status_code == 404
    assert client.put(
        "/api/workspaces/missing",
        headers=headers,
        json={"title": "Missing"},
    ).status_code == 404
    assert client.delete("/api/workspaces/missing", headers=headers).status_code == 404


def test_translated_chapter_returns_not_found_when_result_is_missing(
    client: TestClient,
    novel_chapter_repository: InMemoryNovelChapterRepository,
    translation_repository: InMemoryTranslationRepository,
) -> None:
    headers = _headers(_login(client))
    novel = client.post(
        "/api/novels",
        headers=headers,
        json={"title": "Missing translation result", "language": "zh"},
    ).json()
    novel_chapter_repository.save(_chapter(novel["id"], "chapter-1", 0))
    translation_data = _create_translation(
        client,
        headers,
        novel["id"],
        "Result not persisted",
    )
    translation = translation_repository.get_by_id(translation_data["id"])
    assert translation is not None
    translation = translation_repository.queue_tasks(
        translation.id,
        tasks=[
            TranslationTask(
                id="chapter-1",
                title="Original chapter 1",
                chapter_number=1,
                manifest_index=0,
                source_chapter_updated_at=datetime.now(UTC),
            )
        ],
        force=False,
        etag=translation.etag,
    ).translation
    translation.tasks[0].status = TranslationTaskStatus.COMPLETED
    translation.tasks[0].result_available = True
    translation.progress = TranslationProgress.from_tasks(translation.tasks)
    translation_repository.update(translation, translation.etag)

    response = client.get(
        f"/api/novels/{novel['id']}/chapters/chapter-1?language=vi",
        headers=headers,
    )
    assert response.status_code == 404


def test_workspace_start_and_stop_queue_available_chapters(
    client: TestClient,
    novel_chapter_repository: InMemoryNovelChapterRepository,
    queue_publisher: FakeQueuePublisher,
) -> None:
    headers = _headers(_login(client))
    novel = client.post(
        "/api/novels",
        headers=headers,
        json={"title": "Audio task source", "language": "en"},
    ).json()
    novel_chapter_repository.save(_chapter(novel["id"], "chapter-1", 0))
    novel_chapter_repository.save(_chapter(novel["id"], "chapter-2", 1))
    workspace = client.post(
        "/api/workspaces",
        headers=headers,
        json={
            "title": "Queued audio",
            "type": "audio",
            "novelId": novel["id"],
            "language": "en",
        },
    ).json()

    started = client.patch(
        f"/api/workspaces/{workspace['id']}/start",
        headers=headers,
        json={
            "provider": "Microsoft Foundry",
            "voice": "vi-VN-HoaiMyNeural",
            "chapterIndexFrom": 1,
            "chapterIndexTo": 2,
            "refetch": True,
        },
    )
    assert started.status_code == 202
    detail = started.json()
    assert detail["progress"]["queued"] == 2
    assert [task["status"] for task in detail["tasks"]] == ["queued", "queued"]
    assert all(task["provider"] == "Microsoft Foundry" for task in detail["tasks"])
    assert [name for name, _ in queue_publisher.messages] == [
        "workspaces-tasks",
        "workspaces-tasks",
    ]
    assert queue_publisher.messages[0][1] == {
        "schemaVersion": 1,
        "type": "workspace.task.requested",
        "workspaceId": workspace["id"],
        "createdBy": queue_publisher.messages[0][1]["createdBy"],
        "taskId": "chapter-1",
        "provider": "Microsoft Foundry",
        "voice": "vi-VN-HoaiMyNeural",
        "refetch": True,
        "enqueuedAt": queue_publisher.messages[0][1]["enqueuedAt"],
    }

    stopped = client.patch(
        f"/api/workspaces/{workspace['id']}/stop",
        headers=headers,
    )
    assert stopped.status_code == 200
    assert stopped.json()["progress"]["queued"] == 0
    assert stopped.json()["progress"]["created"] == 2

    assert client.patch(
        f"/api/workspaces/{workspace['id']}/start",
        headers=headers,
        json={
            "provider": "foundry",
            "voice": "voice",
            "chapterIndexFrom": 2,
            "chapterIndexTo": 1,
        },
    ).status_code == 422


def test_workspace_result_and_export_return_chapter_artifacts(
    client: TestClient,
    novel_chapter_repository: InMemoryNovelChapterRepository,
    workspace_repository: InMemoryWorkspaceRepository,
    workspace_result_repository: InMemoryWorkspaceResultRepository,
) -> None:
    headers = _headers(_login(client))
    novel = client.post(
        "/api/novels",
        headers=headers,
        json={"title": "Artifact source", "language": "en"},
    ).json()
    novel_chapter_repository.save(_chapter(novel["id"], "chapter-1", 0))
    workspace_data = client.post(
        "/api/workspaces",
        headers=headers,
        json={
            "title": "Artifact workspace",
            "type": "audio",
            "novelId": novel["id"],
            "language": "en",
        },
    ).json()
    started = client.patch(
        f"/api/workspaces/{workspace_data['id']}/start",
        headers=headers,
        json={
            "provider": "Microsoft Foundry",
            "voice": "voice-1",
            "chapterIndexFrom": 1,
            "chapterIndexTo": 1,
        },
    )
    assert started.status_code == 202

    workspace = workspace_repository.get_by_id(workspace_data["id"])
    assert workspace is not None
    workspace.tasks[0].status = WorkspaceTaskStatus.COMPLETED
    workspace.tasks[0].result_available = True
    workspace.progress = WorkspaceProgress.from_tasks(workspace.tasks)
    workspace_repository.update(workspace, workspace.etag)
    now = datetime.now(UTC)
    workspace_result_repository.upsert(
        WorkspaceResult(
            id="chapter-1",
            workspace_id=workspace.id,
            task_id="chapter-1",
            provider="Microsoft Foundry",
            voice="voice-1",
            content_key=["hash-1", "hash-2"],
            audio_url="https://storage.test/audio.wav",
            subtitle_url="https://storage.test/captions.srt",
            created_at=now,
            updated_at=now,
        )
    )

    result = client.get(
        f"/api/workspaces/{workspace.id}/tasks/chapter-1/result",
        headers=headers,
    )
    assert result.status_code == 200
    assert result.json() == {
        "taskId": "chapter-1",
        "workspaceId": workspace.id,
        "provider": "Microsoft Foundry",
        "voice": "voice-1",
        "audioUrl": "https://storage.test/audio.wav",
        "subtitleUrl": "https://storage.test/captions.srt",
        "createdAt": result.json()["createdAt"],
        "updatedAt": result.json()["updatedAt"],
    }

    exported = client.get(
        f"/api/workspaces/{workspace.id}/tasks/chapter-1/export",
        headers=headers,
    )
    assert exported.status_code == 200
    assert exported.json()["exportUrl"] == "https://storage.test/audio.wav"


def test_workspace_result_rejects_legacy_schema(
    client: TestClient,
    novel_chapter_repository: InMemoryNovelChapterRepository,
    workspace_repository: InMemoryWorkspaceRepository,
    workspace_result_repository: InMemoryWorkspaceResultRepository,
) -> None:
    headers = _headers(_login(client))
    novel = client.post(
        "/api/novels",
        headers=headers,
        json={"title": "Legacy source", "language": "en"},
    ).json()
    novel_chapter_repository.save(_chapter(novel["id"], "chapter-1", 0))
    workspace_data = client.post(
        "/api/workspaces",
        headers=headers,
        json={
            "title": "Legacy workspace",
            "type": "audio",
            "novelId": novel["id"],
            "language": "en",
        },
    ).json()
    client.patch(
        f"/api/workspaces/{workspace_data['id']}/start",
        headers=headers,
        json={
            "provider": "Microsoft Foundry",
            "voice": "voice-1",
            "chapterIndexFrom": 1,
            "chapterIndexTo": 1,
        },
    )
    workspace = workspace_repository.get_by_id(workspace_data["id"])
    assert workspace is not None
    workspace.tasks[0].status = WorkspaceTaskStatus.COMPLETED
    workspace.tasks[0].result_available = True
    workspace.progress = WorkspaceProgress.from_tasks(workspace.tasks)
    workspace_repository.update(workspace, workspace.etag)
    now = datetime.now(UTC)
    workspace_result_repository.upsert(
        WorkspaceResult(
            id="chapter-1",
            workspace_id=workspace.id,
            task_id="chapter-1",
            provider="Microsoft Foundry",
            voice="voice-1",
            schema_version=1,
            content_key=["hash"],
            created_at=now,
            updated_at=now,
        )
    )

    response = client.get(
        f"/api/workspaces/{workspace.id}/tasks/chapter-1/result",
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Workspace task result is obsolete; regenerate the task"
    )

    exported = client.get(
        f"/api/workspaces/{workspace.id}/tasks/chapter-1/export",
        headers=headers,
    )
    assert exported.status_code == 409
    assert exported.json()["detail"] == (
        "Workspace task result is obsolete; regenerate the task"
    )


def _chapter(novel_id: str, chapter_id: str, index: int) -> NovelChapter:
    now = datetime.now(UTC)
    return NovelChapter(
        id=chapter_id,
        novel_id=novel_id,
        scraping_task_id=chapter_id,
        title=f"Original chapter {index + 1}",
        chapter_number=index + 1,
        manifest_index=index,
        source_url=f"https://example.test/{chapter_id}",
        content=["Original line 1", "Original line 2"],
        content_available=True,
        manually_edited=False,
        source_updated=False,
        source_removed=False,
        source_result_updated_at=now,
        created_at=now,
        updated_at=now,
    )


def _create_translation(
    client: TestClient,
    headers: dict[str, str],
    novel_id: str,
    name: str,
) -> dict[str, Any]:
    response = client.post(
        "/api/translations",
        headers=headers,
        json={"name": name, "novelId": novel_id, "targetLanguage": "vi"},
    )
    assert response.status_code == 201
    return response.json()


def _complete_translation(
    translations: InMemoryTranslationRepository,
    results: InMemoryTranslationResultRepository,
    translation_id: str,
    chapter_id: str,
    title: str,
    content: str,
    *,
    updated_at: datetime,
) -> None:
    translation = translations.get_by_id(translation_id)
    assert translation is not None
    translation = translations.queue_tasks(
        translation.id,
        tasks=[
            TranslationTask(
                id=chapter_id,
                title=title,
                chapter_number=1,
                manifest_index=0,
                source_chapter_updated_at=updated_at,
            )
        ],
        force=False,
        etag=translation.etag,
    ).translation
    task = next(item for item in translation.tasks if item.id == chapter_id)
    task.status = TranslationTaskStatus.COMPLETED
    task.result_available = True
    translation.progress = TranslationProgress.from_tasks(translation.tasks)
    translation.updated_at = updated_at
    translations.update(translation, translation.etag)
    results.upsert(
        TranslationResult(
            id=task.id,
            translation_id=translation.id,
            task_id=task.id,
            title=title,
            chapter_number=task.chapter_number,
            content=[content],
            created_at=updated_at,
            updated_at=updated_at,
        )
    )


def _create_member_and_login(client: TestClient, admin_token: str) -> str:
    email = "audio-workspace-member@example.com"
    created = client.post(
        "/api/users",
        headers=_headers(admin_token),
        json={
            "email": email,
            "password": "member-password",
            "displayName": "Audio workspace member",
        },
    )
    assert created.status_code == 201
    return _login(client, email=email, password="member-password")


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
