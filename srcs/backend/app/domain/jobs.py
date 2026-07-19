"""Crawler job domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class JobKind(StrEnum):
    """Supported background job kinds."""

    CRAWL = "crawl"


class JobStatus(StrEnum):
    """Supported background job lifecycle states."""

    QUEUED = "queued"
    PROCESSING = "processing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in {JobStatus.COMPLETED, JobStatus.FAILED}

    @property
    def is_active(self) -> bool:
        return not self.is_terminal


@dataclass(slots=True)
class Job:
    """Persisted background job."""

    id: str
    kind: JobKind
    crawler_id: str
    source_url: str
    idempotency_key: str
    active_key: str
    status: JobStatus
    attempts: int
    last_error: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    etag: str | None = None


@dataclass(frozen=True, slots=True)
class JobCreateResult:
    """Result of an idempotent create-or-return operation."""

    job: Job
    created: bool
