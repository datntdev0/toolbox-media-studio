"""Workspace repository contract and in-memory implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Protocol

from app.domain.workspaces import (
    Workspace,
    WorkspacePage,
    WorkspaceProgress,
    WorkspaceQueueResult,
    WorkspaceTask,
    WorkspaceTaskStatus,
    WorkspaceType,
)


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

    def update(self, workspace: Workspace, etag: str | None = None) -> Workspace: ...

    def delete(self, id: str, deleted_by: str) -> None: ...

    def queue_tasks(
        self,
        id: str,
        *,
        chapter_index_from: int,
        chapter_index_to: int,
        provider: str,
        voice: str,
        force: bool,
        etag: str | None,
    ) -> WorkspaceQueueResult: ...

    def stop_queued_tasks(self, id: str, *, etag: str | None) -> Workspace: ...

    def claim_task(
        self,
        id: str,
        task_id: str,
        *,
        etag: str | None,
    ) -> Workspace | None: ...

    def update_task(
        self,
        id: str,
        task_id: str,
        status: WorkspaceTaskStatus,
        *,
        attempts: int,
        error: str | None,
        result_available: bool,
        completed_at: datetime | None,
        source_chapter_updated_at: datetime | None,
        clear_source_updated: bool,
        etag: str | None,
    ) -> Workspace: ...


class WorkspaceNotFoundError(Exception):
    """Raised when a workspace cannot be found."""


class WorkspaceConflictError(Exception):
    """Raised when optimistic concurrency validation fails."""


class WorkspaceChapterRangeError(ValueError):
    """Raised when a requested range contains no active workspace tasks."""


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

    def update(self, workspace: Workspace, etag: str | None = None) -> Workspace:
        current = self._workspaces.get(workspace.id)
        if current is None or current.deleted_at is not None:
            raise WorkspaceNotFoundError
        if etag is not None and current.etag != etag:
            raise WorkspaceConflictError("Workspace has changed")
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

    def queue_tasks(
        self,
        id: str,
        *,
        chapter_index_from: int,
        chapter_index_to: int,
        provider: str,
        voice: str,
        force: bool,
        etag: str | None,
    ) -> WorkspaceQueueResult:
        workspace = self._require(id)
        self._check_etag(workspace, etag)
        matching = [
            task
            for task in workspace.tasks
            if not task.source_removed
            and chapter_index_from <= task.manifest_index + 1 <= chapter_index_to
        ]
        if not matching:
            raise WorkspaceChapterRangeError(
                "No workspace tasks match the requested chapter index range"
            )
        queued = [
            task
            for task in matching
            if force
            or task.status not in {WorkspaceTaskStatus.QUEUED, WorkspaceTaskStatus.RUNNING}
        ]
        for task in queued:
            task.status = WorkspaceTaskStatus.QUEUED
            task.last_error = None
            task.provider = provider
            task.voice = voice
        if queued:
            self._touch(workspace)
        return WorkspaceQueueResult(
            workspace=deepcopy(workspace),
            tasks=deepcopy(queued),
        )

    def stop_queued_tasks(self, id: str, *, etag: str | None) -> Workspace:
        workspace = self._require(id)
        self._check_etag(workspace, etag)
        for task in workspace.tasks:
            if task.status == WorkspaceTaskStatus.QUEUED:
                task.status = WorkspaceTaskStatus.CREATED
        self._touch(workspace)
        return deepcopy(workspace)

    def claim_task(
        self,
        id: str,
        task_id: str,
        *,
        etag: str | None,
    ) -> Workspace | None:
        workspace = self._require(id)
        self._check_etag(workspace, etag)
        task = self._require_task(workspace, task_id)
        if task.source_removed or task.status != WorkspaceTaskStatus.QUEUED:
            return None
        task.status = WorkspaceTaskStatus.RUNNING
        task.attempts += 1
        task.last_error = None
        self._touch(workspace)
        return deepcopy(workspace)

    def update_task(
        self,
        id: str,
        task_id: str,
        status: WorkspaceTaskStatus,
        *,
        attempts: int,
        error: str | None,
        result_available: bool,
        completed_at: datetime | None,
        source_chapter_updated_at: datetime | None,
        clear_source_updated: bool,
        etag: str | None,
    ) -> Workspace:
        workspace = self._require(id)
        self._check_etag(workspace, etag)
        task = self._require_task(workspace, task_id)
        task.status = status
        task.attempts = max(task.attempts, attempts)
        task.last_error = error
        task.result_available = result_available
        task.completed_at = completed_at
        if source_chapter_updated_at is not None:
            task.source_chapter_updated_at = source_chapter_updated_at
        if clear_source_updated:
            task.source_updated = False
        self._touch(workspace)
        return deepcopy(workspace)

    def _require(self, id: str) -> Workspace:
        workspace = self._workspaces.get(id)
        if workspace is None or workspace.deleted_at is not None:
            raise WorkspaceNotFoundError
        return workspace

    @staticmethod
    def _require_task(workspace: Workspace, task_id: str) -> WorkspaceTask:
        task = next((item for item in workspace.tasks if item.id == task_id), None)
        if task is None:
            raise WorkspaceNotFoundError
        return task

    @staticmethod
    def _check_etag(workspace: Workspace, etag: str | None) -> None:
        if etag is not None and workspace.etag != etag:
            raise WorkspaceConflictError("Workspace has changed")

    def _touch(self, workspace: Workspace) -> None:
        workspace.progress = WorkspaceProgress.from_tasks(workspace.tasks)
        workspace.updated_at = datetime.now(UTC)
        workspace.etag = self._next_etag()

    @staticmethod
    def _next_etag() -> str:
        return datetime.now(UTC).isoformat()
