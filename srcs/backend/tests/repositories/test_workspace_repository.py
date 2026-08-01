"""Workspace repository tests."""

from datetime import UTC, datetime

import pytest

from app.domain.workspaces import (
    Workspace,
    WorkspaceProgress,
    WorkspaceTask,
    WorkspaceTaskStatus,
    WorkspaceType,
)
from app.repositories.cosmosdb.cosmos_workspace_repository import CosmosWorkspaceRepository
from app.repositories.workspace_repository import (
    InMemoryWorkspaceRepository,
    WorkspaceConflictError,
    WorkspaceContinuationTokenError,
)


def _workspace(id: str, *, title: str | None = None) -> Workspace:
    now = datetime.now(UTC)
    return Workspace(
        id=id,
        title=title or id,
        type=WorkspaceType.AUDIO,
        novel_id="novel-1",
        language="en",
        created_by="user-1",
        created_at=now,
        updated_by="user-1",
        updated_at=now,
    )


def test_workspace_repository_crud_pagination_and_soft_deletion() -> None:
    repository = InMemoryWorkspaceRepository()
    first = repository.create(_workspace("workspace-1"))
    repository.create(_workspace("workspace-2"))

    page = repository.list(WorkspaceType.AUDIO, 1, None)
    assert len(page.items) == 1
    assert page.continuation_token == "1"
    second_page = repository.list(
        WorkspaceType.AUDIO,
        1,
        page.continuation_token,
    )
    assert len(second_page.items) == 1
    assert second_page.items[0].id != page.items[0].id

    first.title = "Updated"
    updated = repository.update(first)
    assert updated.title == "Updated"

    repository.delete(first.id, "user-2")
    assert repository.get_by_id(first.id) is None
    assert all(
        workspace.id != first.id
        for workspace in repository.list(WorkspaceType.AUDIO, 100, None).items
    )

    with pytest.raises(WorkspaceContinuationTokenError):
        repository.list(None, 10, "invalid")


def test_workspace_repository_task_queue_force_stop_and_concurrency() -> None:
    repository = InMemoryWorkspaceRepository()
    workspace = _workspace("workspace-tasks")
    now = datetime.now(UTC)
    workspace.tasks = [
        WorkspaceTask("chapter-1", "One", 1, 0, now),
        WorkspaceTask("chapter-2", "Two", 2, 1, now),
    ]
    workspace.progress = WorkspaceProgress.from_tasks(workspace.tasks)
    created = repository.create(workspace)

    queued = repository.queue_tasks(
        created.id,
        chapter_index_from=1,
        chapter_index_to=2,
        provider="foundry",
        voice="voice-1",
        force=False,
        etag=created.etag,
    )
    assert len(queued.tasks) == 2
    assert queued.workspace.progress.queued == 2
    claimed = repository.claim_task(
        created.id,
        "chapter-1",
        etag=queued.workspace.etag,
    )
    assert claimed is not None
    assert claimed.tasks[0].status == WorkspaceTaskStatus.RUNNING

    forced = repository.queue_tasks(
        created.id,
        chapter_index_from=1,
        chapter_index_to=1,
        provider="foundry",
        voice="voice-2",
        force=True,
        etag=claimed.etag,
    )
    assert forced.tasks[0].voice == "voice-2"
    stopped = repository.stop_queued_tasks(created.id, etag=forced.workspace.etag)
    assert stopped.tasks[0].status == WorkspaceTaskStatus.CREATED

    with pytest.raises(WorkspaceConflictError):
        repository.stop_queued_tasks(created.id, etag="stale")


def test_cosmos_workspace_deserializes_legacy_documents_without_tasks() -> None:
    now = datetime.now(UTC)
    workspace = CosmosWorkspaceRepository._deserialize(
        {
            "id": "legacy",
            "title": "Legacy audio",
            "type": "audio",
            "novelId": "novel-1",
            "language": "en",
            "createdBy": "user-1",
            "createdAt": now.isoformat(),
            "updatedBy": "user-1",
            "updatedAt": now.isoformat(),
        }
    )

    assert workspace.tasks == []
    assert workspace.progress == WorkspaceProgress()
