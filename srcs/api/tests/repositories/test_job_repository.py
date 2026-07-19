"""Job repository and idempotency tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.jobs import Job, JobKind, JobStatus
from app.repositories.job_repository import InMemoryJobRepository


def test_create_or_get_active_reuses_until_terminal() -> None:
    repository = InMemoryJobRepository()

    first = repository.create_or_get_active(_job(created_by="user-1"))
    second = repository.create_or_get_active(_job(created_by="user-1"))
    repository.mark_completed(first.job.id, "user-1")
    third = repository.create_or_get_active(_job(created_by="user-1"))

    assert first.created is True
    assert second.created is False
    assert second.job.id == first.job.id
    assert third.created is True
    assert third.job.id != first.job.id


def test_create_or_get_active_is_scoped_per_user() -> None:
    repository = InMemoryJobRepository()

    first = repository.create_or_get_active(_job(created_by="user-1"))
    second = repository.create_or_get_active(_job(created_by="user-2"))

    assert first.created is True
    assert second.created is True
    assert first.job.id != second.job.id


def test_concurrent_create_or_get_active_creates_one_job() -> None:
    repository = InMemoryJobRepository()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: repository.create_or_get_active(_job()), range(20)))

    assert sum(result.created for result in results) == 1
    assert len({result.job.id for result in results}) == 1


def test_terminal_transition_releases_active_key() -> None:
    repository = InMemoryJobRepository()
    created = repository.create_or_get_active(_job()).job

    completed = repository.mark_completed(created.id, created.created_by)

    assert completed.status == JobStatus.COMPLETED
    assert completed.active_key == f"terminal:{completed.id}"


def _job(created_by: str = "user-1") -> Job:
    now = datetime.now(UTC)
    key = "sha256:test-key"
    return Job(
        id=str(uuid4()),
        kind=JobKind.CRAWL,
        crawler_id="novel543",
        source_url="https://www.novel543.com/0603625457/dir",
        idempotency_key=key,
        active_key=key,
        status=JobStatus.QUEUED,
        attempts=0,
        last_error=None,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
