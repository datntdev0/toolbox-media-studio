"""Workspace repository contract and in-memory implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Protocol

from app.domain.workspaces import Workspace, WorkspacePage, WorkspaceType


class WorkspaceRepository(Protocol):
    """Persistence contract for media workspaces."""

    def create(self, workspace: Workspace) -> Workspace: ...

    def get_by_id(self, id: str) -> Workspace | None: ...

    def list(
        self,
        workspace_type: WorkspaceType | None,
        limit: int,
        continuation_token: str | None,
    ) -> WorkspacePage: ...

    def update(self, workspace: Workspace) -> Workspace: ...

    def delete(self, id: str, deleted_by: str) -> None: ...


class WorkspaceNotFoundError(Exception):
    """Raised when a workspace cannot be found."""


class WorkspaceContinuationTokenError(ValueError):
    """Raised when a workspace continuation token is invalid."""


class InMemoryWorkspaceRepository:
    """In-memory workspace persistence for tests."""

    def __init__(self) -> None:
        self._workspaces: dict[str, Workspace] = {}

    def create(self, workspace: Workspace) -> Workspace:
        stored = deepcopy(workspace)
        stored.etag = self._next_etag()
        self._workspaces[stored.id] = stored
        return deepcopy(stored)

    def get_by_id(self, id: str) -> Workspace | None:
        workspace = self._workspaces.get(id)
        if workspace is None or workspace.deleted_at is not None:
            return None
        return deepcopy(workspace)

    def list(
        self,
        workspace_type: WorkspaceType | None,
        limit: int,
        continuation_token: str | None,
    ) -> WorkspacePage:
        try:
            offset = int(continuation_token or "0")
        except ValueError as exc:
            raise WorkspaceContinuationTokenError("Invalid continuation token") from exc
        if offset < 0:
            raise WorkspaceContinuationTokenError("Invalid continuation token")

        workspaces = [
            deepcopy(workspace)
            for workspace in self._workspaces.values()
            if workspace.deleted_at is None
            and (workspace_type is None or workspace.type == workspace_type)
        ]
        workspaces.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        page = workspaces[offset : offset + limit]
        next_offset = offset + len(page)
        return WorkspacePage(
            items=page,
            continuation_token=str(next_offset) if next_offset < len(workspaces) else None,
        )

    def update(self, workspace: Workspace) -> Workspace:
        current = self._workspaces.get(workspace.id)
        if current is None or current.deleted_at is not None:
            raise WorkspaceNotFoundError
        stored = deepcopy(workspace)
        stored.etag = self._next_etag()
        self._workspaces[stored.id] = stored
        return deepcopy(stored)

    def delete(self, id: str, deleted_by: str) -> None:
        workspace = self._workspaces.get(id)
        if workspace is None or workspace.deleted_at is not None:
            raise WorkspaceNotFoundError
        now = datetime.now(UTC)
        workspace.deleted_at = now
        workspace.deleted_by = deleted_by
        workspace.updated_at = now
        workspace.updated_by = deleted_by
        workspace.etag = self._next_etag()

    @staticmethod
    def _next_etag() -> str:
        return datetime.now(UTC).isoformat()
