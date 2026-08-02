"""Translation project domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.novels import Novel


class TranslationStatus(StrEnum):
    """Translation lifecycle and processing states."""

    NEEDS_SETUP = "needs_setup"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"
    DELETED = "deleted"


class TranslationTaskStatus(StrEnum):
    """Embedded translation task lifecycle states."""

    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class TranslationTask:
    """One source novel chapter tracked by a translation."""

    id: str
    title: str
    chapter_number: int | None
    manifest_index: int
    source_chapter_updated_at: datetime
    status: TranslationTaskStatus = TranslationTaskStatus.CREATED
    attempts: int = 0
    last_error: str | None = None
    result_available: bool = False
    completed_at: datetime | None = None
    source_updated: bool = False
    source_removed: bool = False


@dataclass(slots=True)
class TranslationProgress:
    """Rollup counters stored with a translation."""

    total: int = 0
    created: int = 0
    queued: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0

    @classmethod
    def from_tasks(cls, tasks: list[TranslationTask]) -> TranslationProgress:
        counts = {status: 0 for status in TranslationTaskStatus}
        for task in tasks:
            if task.source_removed:
                continue
            counts[task.status] += 1
        return cls(
            total=sum(counts.values()),
            created=counts[TranslationTaskStatus.CREATED],
            queued=counts[TranslationTaskStatus.QUEUED],
            running=counts[TranslationTaskStatus.RUNNING],
            completed=counts[TranslationTaskStatus.COMPLETED],
            failed=counts[TranslationTaskStatus.FAILED],
        )


@dataclass(slots=True)
class TranslationConfiguration:
    """AI configuration persisted with a translation project."""

    provider_id: str
    model_id: str
    global_prompt: str


@dataclass(slots=True)
class Translation:
    """Persisted translation project."""

    id: str
    name: str
    novel_id: str
    target_language: str
    configuration: TranslationConfiguration | None
    status: TranslationStatus
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    tasks: list[TranslationTask] = field(default_factory=list)
    progress: TranslationProgress = field(default_factory=TranslationProgress)
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    etag: str | None = None


@dataclass(slots=True)
class TranslationPage:
    """Paged translation list result."""

    items: list[Translation]
    continuation_token: str | None


@dataclass(slots=True)
class TranslationView:
    """Translation project enriched with its current novel."""

    translation: Translation
    novel: Novel | None


@dataclass(slots=True)
class TranslationViewPage:
    """Paged enriched translation list."""

    items: list[TranslationView]
    continuation_token: str | None


@dataclass(frozen=True, slots=True)
class TranslationQueueResult:
    """Result of queueing a translation chapter range."""

    translation: Translation
    tasks: list[TranslationTask]
