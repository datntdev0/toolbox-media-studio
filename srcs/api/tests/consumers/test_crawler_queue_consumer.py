"""Crawler queue consumer tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.consumers.crawler_queue_consumer import CrawlerJobProcessor, CrawlerQueueConsumer
from app.domain.jobs import Job, JobKind, JobStatus
from app.providers.queue_provider import QueueProvider, ReceivedQueueMessage, SentQueueMessage
from app.repositories.job_repository import InMemoryJobRepository


class FailingProcessor(CrawlerJobProcessor):
    """Processor that always fails."""

    def process(self, crawler_id: str, url: str) -> None:
        del crawler_id, url
        raise RuntimeError("boom")


class RecordingQueue:
    """Queue fake that records retry/delete/send calls."""

    def __init__(self, queue_name: str) -> None:
        self._queue_name = queue_name
        self.sent: list[Mapping[str, object]] = []
        self.deleted: list[str] = []
        self.raise_on_send: Exception | None = None

    @property
    def queue_name(self) -> str:
        return self._queue_name

    def ensure_exists(self) -> None:
        return None

    def send(self, message: Mapping[str, object]) -> SentQueueMessage:
        if self.raise_on_send is not None:
            raise self.raise_on_send
        self.sent.append(dict(message))
        return SentQueueMessage(id=str(len(self.sent)))

    def receive_one(self, visibility_timeout: int) -> ReceivedQueueMessage | None:
        del visibility_timeout
        return None

    def retry(self, message: ReceivedQueueMessage, visibility_timeout: int) -> None:
        del message, visibility_timeout

    def delete(self, message: ReceivedQueueMessage) -> None:
        self.deleted.append(message.id)


class RecordingQueueFactory:
    """Factory fake for concrete consumer construction."""

    def __init__(self, source: RecordingQueue, dlq: RecordingQueue) -> None:
        self.source = source
        self.dlq = dlq

    def get(self, queue_name: str) -> QueueProvider:
        if queue_name == "crawler-jobs":
            return self.source
        if queue_name == "crawler-jobs-dead-letter":
            return self.dlq
        raise KeyError(queue_name)


def test_sixth_failure_dead_letters_marks_failed_then_deletes() -> None:
    repository = InMemoryJobRepository()
    job = repository.create_or_get_active(_job()).job
    source = RecordingQueue("crawler-jobs")
    dlq = RecordingQueue("crawler-jobs-dead-letter")
    consumer = _consumer(source, dlq, repository)

    consumer._process_message(_message(job, dequeue_count=6), "consumer-0")

    stored = repository.get(job.id, job.created_by)
    assert stored is not None
    assert stored.status == JobStatus.FAILED
    assert len(dlq.sent) == 1
    assert source.deleted == ["message-1"]


def test_dead_letter_send_failure_keeps_source_message_and_active_job() -> None:
    repository = InMemoryJobRepository()
    job = repository.create_or_get_active(_job()).job
    source = RecordingQueue("crawler-jobs")
    dlq = RecordingQueue("crawler-jobs-dead-letter")
    dlq.raise_on_send = RuntimeError("dlq down")
    consumer = _consumer(source, dlq, repository)

    with pytest.raises(RuntimeError, match="dlq down"):
        consumer._process_message(_message(job, dequeue_count=6), "consumer-0")

    stored = repository.get(job.id, job.created_by)
    assert stored is not None
    assert stored.status == JobStatus.PROCESSING
    assert source.deleted == []


def _consumer(
    source: QueueProvider,
    dlq: QueueProvider,
    repository: InMemoryJobRepository,
) -> CrawlerQueueConsumer:
    return CrawlerQueueConsumer(
        job_repository=repository,
        queue_provider_factory=RecordingQueueFactory(source, dlq),
        processor=FailingProcessor(),
    )


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


def _message(job: Job, dequeue_count: int) -> ReceivedQueueMessage:
    return ReceivedQueueMessage(
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
