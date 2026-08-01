"""Workspace result repository contract and in-memory implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol

from app.domain.workspace_results import WorkspaceResult


class WorkspaceResultRepository(Protocol):
    """Persistence contract for one result per workspace task."""

    def get(self, workspace_id: str, task_id: str) -> WorkspaceResult | None: ...

    def upsert(self, result: WorkspaceResult) -> WorkspaceResult: ...

    def delete_by_workspace(self, workspace_id: str) -> None: ...


class InMemoryWorkspaceResultRepository:
    """Thread-safe in-memory workspace result persistence."""

    def __init__(self) -> None:
        self._results: dict[tuple[str, str], WorkspaceResult] = {}
        self._lock = Lock()

    def get(self, workspace_id: str, task_id: str) -> WorkspaceResult | None:
        with self._lock:
            result = self._results.get((workspace_id, task_id))
            return deepcopy(result) if result is not None else None

    def upsert(self, result: WorkspaceResult) -> WorkspaceResult:
        if result.id != result.task_id:
            raise ValueError("WorkspaceResult id must equal taskId")
        with self._lock:
            stored = deepcopy(result)
            current = self._results.get((stored.workspace_id, stored.task_id))
            if current is not None:
                stored.created_at = current.created_at
            stored.updated_at = datetime.now(UTC)
            stored.etag = stored.updated_at.isoformat()
            self._results[(stored.workspace_id, stored.task_id)] = stored
            return deepcopy(stored)

    def delete_by_workspace(self, workspace_id: str) -> None:
        with self._lock:
            keys = [key for key in self._results if key[0] == workspace_id]
            for key in keys:
                del self._results[key]
