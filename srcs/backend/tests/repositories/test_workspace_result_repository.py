"""Workspace result repository tests."""

from datetime import UTC, datetime

from app.domain.workspace_results import WorkspaceResult
from app.repositories.cosmosdb.cosmos_workspace_result_repository import (
    WORKSPACE_RESULTS_CONTAINER_NAME,
    CosmosWorkspaceResultRepository,
)
from app.repositories.workspace_result_repository import InMemoryWorkspaceResultRepository


def test_workspace_result_upsert_and_delete() -> None:
    repository = InMemoryWorkspaceResultRepository()
    now = datetime.now(UTC)
    created = repository.upsert(
        WorkspaceResult(
            id="chapter-1",
            workspace_id="workspace-1",
            task_id="chapter-1",
            provider="foundry",
            voice="voice-1",
            content_key=["first"],
            audio_url="https://storage.test/audio.wav",
            subtitle_url="https://storage.test/captions.srt",
            created_at=now,
            updated_at=now,
        )
    )
    created.content_key.append("second")
    updated = repository.upsert(created)

    assert updated.content_key == ["first", "second"]
    assert updated.created_at == created.created_at
    repository.delete_by_workspace("workspace-1")
    assert repository.get("workspace-1", "chapter-1") is None


def test_cosmos_workspace_result_wire_shape() -> None:
    now = datetime.now(UTC)
    item = CosmosWorkspaceResultRepository._serialize(
        WorkspaceResult(
            id="chapter-1",
            workspace_id="workspace-1",
            task_id="chapter-1",
            provider="foundry",
            voice="voice-1",
            content_key=["hash"],
            audio_url="https://storage.test/audio.wav",
            subtitle_url="https://storage.test/captions.srt",
            created_at=now,
            updated_at=now,
        )
    )

    assert WORKSPACE_RESULTS_CONTAINER_NAME == "domain.workspace_results"
    assert item["id"] == "chapter-1"
    assert item["workspaceId"] == "workspace-1"
    assert item["schemaVersion"] == 2
    assert item["contentKey"] == ["hash"]
    assert item["audioUrl"] == "https://storage.test/audio.wav"
    assert item["subtitleUrl"] == "https://storage.test/captions.srt"
    assert "audioUrls" not in item


def test_cosmos_workspace_result_deserializes_legacy_result_as_obsolete() -> None:
    now = datetime.now(UTC)
    result = CosmosWorkspaceResultRepository._deserialize(
        {
            "id": "chapter-1",
            "workspaceId": "workspace-1",
            "taskId": "chapter-1",
            "provider": "foundry",
            "voice": "voice-1",
            "contentKey": ["hash"],
            "audioUrls": ["https://storage.test/0.wav"],
            "createdAt": now.isoformat(),
            "updatedAt": now.isoformat(),
        }
    )

    assert result.schema_version == 1
    assert result.audio_url is None
    assert result.subtitle_url is None
    assert result.artifacts_available is False
