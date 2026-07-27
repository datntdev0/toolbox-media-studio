"""Workspace repository contract and in-memory implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Protocol

from app.domain.workspaces import Workspace, WorkspaceKind, WorkspacePage, WorkspaceStatus


class WorkspaceRepository(Protocol):
    """Persistence contract for workspace records."""

    def create(self, workspace: Workspace) -> Workspace: ...

    def get_by_id(self, id: str) -> Workspace | None: ...

    def list(
        self,
        kind: WorkspaceKind | None,
        limit: int,
        continuation_token: str | None,
    ) -> WorkspacePage: ...

    def update(self, workspace: Workspace, etag: str | None) -> Workspace: ...

    def delete(self, id: str, etag: str | None, deleted_by: str) -> None: ...


class WorkspaceNotFoundError(Exception):
    """Raised when a workspace cannot be found."""


class WorkspaceConflictError(Exception):
    """Raised when optimistic concurrency validation fails."""


class WorkspaceContinuationTokenError(ValueError):
    """Raised when an in-memory continuation token is invalid."""


class InMemoryWorkspaceRepository:
    """Simple workspace repository used by route tests."""

    def __init__(self) -> None:
        self._workspaces: dict[str, Workspace] = {}

    def create(self, workspace: Workspace) -> Workspace:
        stored = deepcopy(workspace)
        stored.etag = self._next_etag()
        self._workspaces[stored.id] = stored
        return deepcopy(stored)

    def get_by_id(self, id: str) -> Workspace | None:
        workspace = self._workspaces.get(id)
        if workspace is None or workspace.status == WorkspaceStatus.DELETED:
            return None
        return deepcopy(workspace)

    def list(
        self,
        kind: WorkspaceKind | None,
        limit: int,
        continuation_token: str | None,
    ) -> WorkspacePage:
        try:
            offset = int(continuation_token or "0")
        except ValueError as exc:
            raise WorkspaceContinuationTokenError("Invalid continuation token") from exc

        workspaces = [
            deepcopy(workspace)
            for workspace in self._workspaces.values()
            if workspace.status != WorkspaceStatus.DELETED
            and (kind is None or workspace.kind == kind)
        ]
        workspaces.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        page = workspaces[offset : offset + limit]
        next_offset = offset + len(page)
        next_token = str(next_offset) if next_offset < len(workspaces) else None
        return WorkspacePage(items=page, continuation_token=next_token)

    def update(self, workspace: Workspace, etag: str | None) -> Workspace:
        current = self._workspaces.get(workspace.id)
        if current is None or current.status == WorkspaceStatus.DELETED:
            raise WorkspaceNotFoundError
        if current.kind != workspace.kind:
            raise WorkspaceConflictError("Workspace kind cannot be changed")
        if etag is not None and current.etag != etag:
            raise WorkspaceConflictError("Workspace has changed")

        stored = deepcopy(workspace)
        stored.etag = self._next_etag()
        self._workspaces[stored.id] = stored
        return deepcopy(stored)

    def delete(self, id: str, etag: str | None, deleted_by: str) -> None:
        workspace = self._workspaces.get(id)
        if workspace is None or workspace.status == WorkspaceStatus.DELETED:
            raise WorkspaceNotFoundError
        if etag is not None and workspace.etag != etag:
            raise WorkspaceConflictError("Workspace has changed")

        now = datetime.now(UTC)
        workspace.status = WorkspaceStatus.DELETED
        workspace.deleted_at = now
        workspace.deleted_by = deleted_by
        workspace.updated_at = now
        workspace.updated_by = deleted_by
        workspace.etag = self._next_etag()

    @staticmethod
    def _next_etag() -> str:
        return datetime.now(UTC).isoformat()
