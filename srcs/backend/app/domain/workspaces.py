"""Workspace domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class WorkspaceKind(StrEnum):
    """Supported workspace project kinds."""

    TRANSLATION = "translation"
    AUDIO = "audio"
    VIDEO = "video"


class WorkspaceStatus(StrEnum):
    """Workspace lifecycle and processing states."""

    NEEDS_SETUP = "needs_setup"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"
    DELETED = "deleted"


@dataclass(slots=True)
class Workspace:
    """Persisted workspace record containing only workspace-owned data."""

    id: str
    name: str
    kind: WorkspaceKind
    novel_id: str
    target_language: str
    status: WorkspaceStatus
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    etag: str | None = None


@dataclass(slots=True)
class WorkspacePage:
    """Paged workspace list result."""

    items: list[Workspace]
    continuation_token: str | None
