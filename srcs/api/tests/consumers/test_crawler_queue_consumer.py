"""Crawler queue consumer tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.consumers.crawler_queue_consumer import CrawlerJobProcessor, CrawlerQueueMessageHandler
from app.core.events.message_handler import QueueMessage
from app.domain.jobs import Job, JobKind, JobStatus
from app.repositories.job_repository import InMemoryJobRepository


class FailingProcessor(CrawlerJobProcessor):
    """Processor that always fails."""

    def process(self, crawler_id: str, url: str) -> None:
        del crawler_id, url
        raise RuntimeError("boom")


def test_processing_failure_marks_retrying_before_reraising() -> None:
    repository = InMemoryJobRepository()
    job = repository.create_or_get_active(_job()).job
    handler = CrawlerQueueMessageHandler(repository, FailingProcessor())

    with pytest.raises(RuntimeError, match="boom"):
        handler.handle(_message(job, dequeue_count=2))

    stored = repository.get(job.id, job.created_by)
    assert stored is not None
    assert stored.status == JobStatus.RETRYING
    assert stored.attempts == 2
    assert stored.last_error == "boom"


def test_mark_failed_transitions_job_to_failed() -> None:
    repository = InMemoryJobRepository()
    job = repository.create_or_get_active(_job()).job
    handler = CrawlerQueueMessageHandler(repository, FailingProcessor())

    handler.mark_failed(_message(job, dequeue_count=6), "boom")

    stored = repository.get(job.id, job.created_by)
    assert stored is not None
    assert stored.status == JobStatus.FAILED
    assert stored.attempts == 6
    assert stored.last_error == "boom"


def _job() -> Job:
    now = datetime.now(UTC)
    return Job(
        id=str(uuid4()),
        kind=JobKind.CRAWL,
        crawler_id="novel543",
        source_url="https://www.novel543.com/0603625457/dir",
        idempotency_key="sha256:test",
        active_key="sha256:test",
        status=JobStatus.QUEUED,
        attempts=0,
        last_error=None,
        created_by="user-1",
        created_at=now,
        updated_at=now,
    )


def _message(job: Job, dequeue_count: int) -> QueueMessage:
    return QueueMessage(
        id="message-1",
        pop_receipt="receipt",
        dequeue_count=dequeue_count,
        content={
            "schemaVersion": 1,
            "kind": "crawl",
            "jobId": job.id,
            "crawlerId": job.crawler_id,
            "url": job.source_url,
            "createdBy": job.created_by,
            "idempotencyKey": job.idempotency_key,
            "enqueuedAt": now_iso(),
        },
    )


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
