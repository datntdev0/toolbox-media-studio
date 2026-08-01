"""Generic media workspace domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.novels import Novel, NovelChapter


class WorkspaceType(StrEnum):
    """Supported media workspace types."""

    AUDIO = "audio"


class WorkspaceSourceType(StrEnum):
    """Kinds of novel content selected by a workspace."""

    ORIGINAL = "original"
    TRANSLATION = "translation"


class WorkspaceTaskStatus(StrEnum):
    """Lifecycle states for one audio chapter task."""

    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class WorkspaceTask:
    """One language-aware chapter tracked by an audio workspace."""

    id: str
    title: str
    chapter_number: int | None
    manifest_index: int
    source_chapter_updated_at: datetime
    status: WorkspaceTaskStatus = WorkspaceTaskStatus.CREATED
    attempts: int = 0
    last_error: str | None = None
    result_available: bool = False
    completed_at: datetime | None = None
    source_updated: bool = False
    source_removed: bool = False
    provider: str | None = None
    voice: str | None = None


@dataclass(slots=True)
class WorkspaceProgress:
    """Persisted rollup counters for workspace tasks."""

    total: int = 0
    created: int = 0
    queued: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0

    @classmethod
    def from_tasks(cls, tasks: list[WorkspaceTask]) -> WorkspaceProgress:
        counts = {status: 0 for status in WorkspaceTaskStatus}
        for task in tasks:
            if task.source_removed:
                continue
            counts[task.status] += 1
        return cls(
            total=sum(counts.values()),
            created=counts[WorkspaceTaskStatus.CREATED],
            queued=counts[WorkspaceTaskStatus.QUEUED],
            running=counts[WorkspaceTaskStatus.RUNNING],
            completed=counts[WorkspaceTaskStatus.COMPLETED],
            failed=counts[WorkspaceTaskStatus.FAILED],
        )


@dataclass(slots=True)
class Workspace:
    """Persisted media workspace."""

    id: str
    title: str
    type: WorkspaceType
    novel_id: str
    language: str
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    tasks: list[WorkspaceTask] = field(default_factory=list)
    progress: WorkspaceProgress = field(default_factory=WorkspaceProgress)
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    etag: str | None = None


@dataclass(slots=True)
class WorkspacePage:
    """Paged workspace list."""

    items: list[Workspace]
    continuation_token: str | None


@dataclass(slots=True)
class WorkspaceView:
    """Workspace enriched with its current novel and selected source."""

    workspace: Workspace
    novel: Novel | None
    source_type: WorkspaceSourceType
    source_available: bool
    chapters: list[NovelChapter]


@dataclass(frozen=True, slots=True)
class WorkspaceQueueResult:
    """Workspace and task snapshots selected for publication."""

    workspace: Workspace
    tasks: list[WorkspaceTask]
