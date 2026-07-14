"""Job repository contracts and in-memory implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol

from app.domain.jobs import Job, JobCreateResult, JobStatus


class JobRepository(Protocol):
    """Persistence contract for background jobs."""

    def create_or_get_active(self, candidate: Job) -> JobCreateResult: ...

    def get(self, id: str, created_by: str) -> Job | None: ...

    def mark_processing(self, id: str, created_by: str, attempt: int) -> Job: ...

    def mark_retrying(self, id: str, created_by: str, attempt: int, error: str) -> Job: ...

    def mark_completed(self, id: str, created_by: str) -> Job: ...

    def mark_failed(self, id: str, created_by: str, attempt: int, error: str) -> Job: ...


class JobNotFoundError(Exception):
    """Raised when a job cannot be found."""


class JobConflictError(Exception):
    """Raised when a job transition conflicts with current state."""


class InMemoryJobRepository:
    """Thread-safe in-memory repository used by tests."""

    def __init__(self) -> None:
        self._jobs: dict[tuple[str, str], Job] = {}
        self._lock = Lock()

    def create_or_get_active(self, candidate: Job) -> JobCreateResult:
        with self._lock:
            active = self._find_active(candidate.created_by, candidate.idempotency_key)
            if active is not None:
                return JobCreateResult(job=deepcopy(active), created=False)

            stored = deepcopy(candidate)
            stored.active_key = stored.idempotency_key
            stored.etag = self._next_etag()
            self._jobs[(stored.created_by, stored.id)] = stored
            return JobCreateResult(job=deepcopy(stored), created=True)

    def get(self, id: str, created_by: str) -> Job | None:
        with self._lock:
            job = self._jobs.get((created_by, id))
            return deepcopy(job) if job is not None else None

    def mark_processing(self, id: str, created_by: str, attempt: int) -> Job:
        return self._transition(
            id=id,
            created_by=created_by,
            status=JobStatus.PROCESSING,
            attempt=attempt,
            error=None,
        )

    def mark_retrying(self, id: str, created_by: str, attempt: int, error: str) -> Job:
        return self._transition(
            id=id,
            created_by=created_by,
            status=JobStatus.RETRYING,
            attempt=attempt,
            error=error,
        )

    def mark_completed(self, id: str, created_by: str) -> Job:
        return self._transition(
            id=id,
            created_by=created_by,
            status=JobStatus.COMPLETED,
            attempt=None,
            error=None,
        )

    def mark_failed(self, id: str, created_by: str, attempt: int, error: str) -> Job:
        return self._transition(
            id=id,
            created_by=created_by,
            status=JobStatus.FAILED,
            attempt=attempt,
            error=error,
        )

    def _transition(
        self,
        *,
        id: str,
        created_by: str,
        status: JobStatus,
        attempt: int | None,
        error: str | None,
    ) -> Job:
        with self._lock:
            job = self._jobs.get((created_by, id))
            if job is None:
                raise JobNotFoundError
            if job.status.is_terminal and status != job.status:
                raise JobConflictError("Terminal jobs cannot transition to another status")

            job.status = status
            if attempt is not None:
                job.attempts = max(job.attempts, attempt)
            job.last_error = error
            job.updated_at = datetime.now(UTC)
            if status.is_terminal:
                job.active_key = f"terminal:{job.id}"
            job.etag = self._next_etag()
            return deepcopy(job)

    def _find_active(self, created_by: str, idempotency_key: str) -> Job | None:
        for job in self._jobs.values():
            if (
                job.created_by == created_by
                and job.idempotency_key == idempotency_key
                and job.status.is_active
            ):
                return job
        return None

    @staticmethod
    def _next_etag() -> str:
        return datetime.now(UTC).isoformat()
