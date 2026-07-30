"""Workspace repository tests."""

from datetime import UTC, datetime

import pytest

from app.domain.workspaces import Workspace, WorkspaceType
from app.repositories.workspace_repository import (
    InMemoryWorkspaceRepository,
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
