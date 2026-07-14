"""Crawler queue consumer."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from app.consumers.queue_consumer import QueueMessageHandler, RetryPolicy, ScheduledQueueConsumer
from app.core.logging import get_logger
from app.domain.jobs import JobStatus
from app.providers.queue_provider import QueueProvider, QueueProviderFactory, ReceivedQueueMessage
from app.repositories.job_repository import JobRepository

logger = get_logger("crawler_queue_consumer")

CRAWLER_QUEUE_NAME = "crawler-jobs"
CRAWLER_QUEUE_DEAD_LETTER_NAME = "crawler-jobs-dead-letter"
CRAWLER_QUEUE_CONSUMER_COUNT = 2
CRAWLER_QUEUE_POLL_INTERVAL_SECONDS = 5
CRAWLER_QUEUE_VISIBILITY_TIMEOUT_SECONDS = 60
CRAWLER_JOB_PROCESSING_SECONDS = 30


class CrawlerJobProcessor(Protocol):
    """Process one crawler job."""

    def process(self, crawler_id: str, url: str) -> None: ...


@dataclass(frozen=True, slots=True)
class SleepingCrawlerJobProcessor:
    """Placeholder crawler processor for this slice."""

    processing_seconds: int = 30

    def process(self, crawler_id: str, url: str) -> None:
        del crawler_id, url
        time.sleep(self.processing_seconds)
        logger.info("Processed crawler job (sleeping for %d seconds)", self.processing_seconds)


class CrawlerQueueMessageHandler(QueueMessageHandler):
    """Validate and process crawler queue messages."""

    def __init__(self, job_repository: JobRepository, processor: CrawlerJobProcessor) -> None:
        self._job_repository = job_repository
        self._processor = processor

    def handle(self, message: ReceivedQueueMessage) -> None:
        payload = CrawlerQueueMessage.from_mapping(message.content)
        job = self._job_repository.get(payload.job_id, payload.created_by)
        if job is None:
            raise ValueError("Crawler job does not exist")
        if job.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
            return

        attempt = max(message.dequeue_count, 1)
        self._job_repository.mark_processing(payload.job_id, payload.created_by, attempt)
        try:
            self._processor.process(payload.crawler_id, payload.url)
        except Exception as exc:
            error = _sanitize_error(exc)
            if attempt < 6:
                self._job_repository.mark_retrying(
                    payload.job_id,
                    payload.created_by,
                    attempt,
                    error,
                )
            raise
        self._job_repository.mark_completed(payload.job_id, payload.created_by)

    def mark_failed(self, message: ReceivedQueueMessage, error: str) -> None:
        """Mark the job failed after the dead-letter send succeeds."""

        payload = CrawlerQueueMessage.from_mapping(message.content)
        attempt = max(message.dequeue_count, 1)
        self._job_repository.mark_failed(payload.job_id, payload.created_by, attempt, error)


@dataclass(frozen=True, slots=True)
class CrawlerQueueMessage:
    """Typed crawler queue message contract."""

    schema_version: int
    kind: str
    job_id: str
    crawler_id: str
    url: str
    created_by: str
    idempotency_key: str
    enqueued_at: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> CrawlerQueueMessage:
        if payload.get("schemaVersion") != 1 or payload.get("kind") != "crawl":
            raise ValueError("Unsupported crawler queue message")
        return cls(
            schema_version=1,
            kind="crawl",
            job_id=_required_str(payload, "jobId"),
            crawler_id=_required_str(payload, "crawlerId"),
            url=_required_str(payload, "url"),
            created_by=_required_str(payload, "createdBy"),
            idempotency_key=_required_str(payload, "idempotencyKey"),
            enqueued_at=_required_str(payload, "enqueuedAt"),
        )


class CrawlerQueueConsumer(ScheduledQueueConsumer):
    """Scheduled crawler-job queue consumer."""

    @staticmethod
    def source_queue_provider(queue_provider_factory: QueueProviderFactory) -> QueueProvider:
        """Return the crawler source queue provider."""

        return queue_provider_factory.get(CRAWLER_QUEUE_NAME)

    @staticmethod
    def ensure_queues(queue_provider_factory: QueueProviderFactory) -> None:
        """Ensure crawler source and dead-letter queues exist."""

        CrawlerQueueConsumer.source_queue_provider(queue_provider_factory).ensure_exists()
        queue_provider_factory.get(CRAWLER_QUEUE_DEAD_LETTER_NAME).ensure_exists()

    def __init__(
        self,
        *,
        job_repository: JobRepository,
        queue_provider_factory: QueueProviderFactory,
        processor: CrawlerJobProcessor | None = None,
    ) -> None:
        source_queue = queue_provider_factory.get(CRAWLER_QUEUE_NAME)
        dead_letter_queue = queue_provider_factory.get(CRAWLER_QUEUE_DEAD_LETTER_NAME)
        super().__init__(
            name="crawler-jobs-consumer",
            source_queue=source_queue,
            dead_letter_queue=dead_letter_queue,
            handler=CrawlerQueueMessageHandler(
                job_repository,
                processor or SleepingCrawlerJobProcessor(CRAWLER_JOB_PROCESSING_SECONDS),
            ),
            retry_policy=RetryPolicy(),
            consumer_count=CRAWLER_QUEUE_CONSUMER_COUNT,
            poll_interval_seconds=CRAWLER_QUEUE_POLL_INTERVAL_SECONDS,
            visibility_timeout_seconds=CRAWLER_QUEUE_VISIBILITY_TIMEOUT_SECONDS,
        )


def _required_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing crawler queue message field: {key}")
    return value


def _sanitize_error(exc: Exception) -> str:
    return (str(exc) or type(exc).__name__)[:500]
