"""Queue handler and listener for Scraping events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from logging import Logger
from typing import Any

from app.core.events.message_handler import MessageHandler, QueueMessage
from app.core.events.polling_queue_publisher import PollingQueuePublisher
from app.core.events.polling_queue_subscriber import PollingQueueSubscriber
from app.domain.scraping_results import ScrapingResult
from app.domain.scrapings import Scraping, ScrapingStatus, ScrapingTask, ScrapingTaskStatus
from app.providers.cache_provider import CacheProvider
from app.providers.crawler_provider import fetch_chapter_content
from app.providers.proxy_service_provider import ProxyProvider
from app.repositories.scraping_repository import (
    ScrapingConflictError,
    ScrapingRepository,
)
from app.repositories.scraping_result_repository import (
    ScrapingResultRepository,
    ScrapingResultTooLargeError,
)

SCRAPING_QUEUE_NAME = "scrapings"
SCRAPING_EVENT_TYPE = "scraping.requested"
SCRAPING_EVENT_SCHEMA_VERSION = 1
SCRAPING_MAX_ATTEMPTS = 3
SCRAPING_STALE_AFTER = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class ScrapingEvent:
    """Validated Scraping queue event."""

    scraping_id: str
    created_by: str
    idempotency_key: str
    attempt: int
    enqueued_at: str

    @classmethod
    def from_mapping(cls, content: Mapping[str, Any]) -> ScrapingEvent:
        if content.get("schemaVersion") != SCRAPING_EVENT_SCHEMA_VERSION:
            raise ValueError("Unsupported Scraping event schema")
        if content.get("type") != SCRAPING_EVENT_TYPE:
            raise ValueError("Unsupported Scraping event type")
        attempt = content.get("attempt", 1)
        if not isinstance(attempt, int) or attempt < 1:
            raise ValueError("Invalid Scraping event attempt")
        return cls(
            scraping_id=_required_string(content, "scrapingId"),
            created_by=_required_string(content, "createdBy"),
            idempotency_key=_required_string(content, "idempotencyKey"),
            attempt=attempt,
            enqueued_at=_required_string(content, "enqueuedAt"),
        )


class ScrapingHandler(MessageHandler):
    """Processes embedded Scraping tasks and persists isolated results."""

    def __init__(
        self,
        logger: Logger,
        scraping_repository: ScrapingRepository,
        scraping_result_repository: ScrapingResultRepository,
        cache_provider: CacheProvider,
        proxy_provider: ProxyProvider,
        queue_publisher: PollingQueuePublisher,
        max_attempts: int = SCRAPING_MAX_ATTEMPTS,
    ) -> None:
        self._logger = logger
        self._scrapings = scraping_repository
        self._results = scraping_result_repository
        self._cache = cache_provider
        self._proxy = proxy_provider
        self._publisher = queue_publisher
        self._max_attempts = max_attempts

    def handle(self, message: QueueMessage) -> None:
        if message.content is None:
            raise ValueError("Scraping queue message has no content")
        event = ScrapingEvent.from_mapping(message.content)
        scraping = self._scrapings.get(event.scraping_id, event.created_by)
        if scraping is None or scraping.status.is_terminal:
            return
        if scraping.idempotency_key != event.idempotency_key:
            raise ValueError("Scraping event idempotency key does not match")

        self._logger.info(
            "Processing Scraping event: %s",
            {
                "messageId": message.id,
                "scrapingId": scraping.id,
                "createdBy": scraping.created_by,
                "attempt": event.attempt,
            },
        )
        scraping = self._set_status_with_retry(
            scraping,
            ScrapingStatus.PROCESSING,
            attempt=event.attempt,
            error=None,
        )

        for task in scraping.tasks:
            if task.status.is_terminal:
                continue
            try:
                scraping = self._process_task(scraping, task)
                self._logger.info(
                    "Scraping task completed %s",
                    {
                        "messageId": message.id,
                        "scrapingId": scraping.id,
                        "taskId": task.id,
                    },
                )
            except Exception as exc:
                scraping = self._record_task_failure(scraping, task.id, exc)

        scraping = self._reconcile_with_retry(scraping)
        if scraping.status == ScrapingStatus.RETRYING:
            try:
                self._publisher.publish(
                    SCRAPING_QUEUE_NAME,
                    build_scraping_event(scraping, attempt=event.attempt + 1),
                )
            except Exception as exc:
                self._set_status_with_retry(
                    scraping,
                    ScrapingStatus.FAILED,
                    attempt=event.attempt,
                    error=_sanitize_error(exc, fallback="Event publication failed"),
                )

    def _process_task(self, scraping: Scraping, task: ScrapingTask) -> Scraping:
        existing = self._results.get(scraping.id, task.id)
        if existing is not None:
            return self._update_task_with_retry(
                scraping,
                task.id,
                ScrapingTaskStatus.COMPLETED,
                attempts=max(task.attempts, 1),
                error=None,
                result_available=True,
                completed_at=existing.created_at,
            )

        scraping = self._update_task_with_retry(
            scraping,
            task.id,
            ScrapingTaskStatus.PROCESSING,
            attempts=task.attempts + 1,
            error=None,
            result_available=False,
            completed_at=None,
        )
        current_task = _find_task(scraping, task.id)
        chapter = fetch_chapter_content(
            crawler_id=scraping.crawler_id,
            chapter_url=current_task.source_url,
            cache_provider=self._cache,
            proxy_provider=self._proxy,
        )
        now = datetime.now(UTC)
        result = self._results.upsert(
            ScrapingResult(
                id=current_task.id,
                scraping_id=scraping.id,
                task_id=current_task.id,
                title=chapter.chapter_title,
                chapter_number=chapter.chapter_number,
                content=chapter.content,
                created_at=now,
                updated_at=now,
            )
        )
        return self._update_task_with_retry(
            scraping,
            current_task.id,
            ScrapingTaskStatus.COMPLETED,
            attempts=current_task.attempts,
            error=None,
            result_available=True,
            completed_at=result.created_at,
        )

    def _record_task_failure(
        self,
        scraping: Scraping,
        task_id: str,
        exc: Exception,
    ) -> Scraping:
        latest = self._scrapings.get(scraping.id, scraping.created_by) or scraping
        task = _find_task(latest, task_id)
        terminal = (
            isinstance(exc, ScrapingResultTooLargeError)
            or task.attempts >= self._max_attempts
        )
        return self._update_task_with_retry(
            latest,
            task.id,
            ScrapingTaskStatus.FAILED if terminal else ScrapingTaskStatus.RETRYING,
            attempts=max(task.attempts, 1),
            error=_sanitize_error(exc),
            result_available=False,
            completed_at=None,
        )

    def _set_status_with_retry(
        self,
        scraping: Scraping,
        status: ScrapingStatus,
        *,
        attempt: int,
        error: str | None,
    ) -> Scraping:
        for _ in range(3):
            try:
                return self._scrapings.set_status(
                    scraping.id,
                    scraping.created_by,
                    status,
                    attempt=attempt,
                    error=error,
                    etag=scraping.etag,
                )
            except ScrapingConflictError:
                scraping = self._scrapings.get(scraping.id, scraping.created_by) or scraping
        raise ScrapingConflictError("Scraping status update conflicted repeatedly")

    def _update_task_with_retry(
        self,
        scraping: Scraping,
        task_id: str,
        status: ScrapingTaskStatus,
        *,
        attempts: int,
        error: str | None,
        result_available: bool,
        completed_at: datetime | None,
    ) -> Scraping:
        for _ in range(3):
            try:
                return self._scrapings.update_task(
                    scraping.id,
                    scraping.created_by,
                    task_id,
                    status,
                    attempts=attempts,
                    error=error,
                    result_available=result_available,
                    completed_at=completed_at,
                    etag=scraping.etag,
                )
            except ScrapingConflictError:
                scraping = self._scrapings.get(scraping.id, scraping.created_by) or scraping
        raise ScrapingConflictError("Scraping task update conflicted repeatedly")

    def _reconcile_with_retry(self, scraping: Scraping) -> Scraping:
        for _ in range(3):
            try:
                return self._scrapings.reconcile(
                    scraping.id,
                    scraping.created_by,
                    etag=scraping.etag,
                )
            except ScrapingConflictError:
                scraping = self._scrapings.get(scraping.id, scraping.created_by) or scraping
        raise ScrapingConflictError("Scraping reconciliation conflicted repeatedly")


class ScrapingQueueListener(PollingQueueSubscriber):
    """Queue listener configured with a ScrapingHandler."""

    def __init__(
        self,
        logger: Logger,
        scraping_repository: ScrapingRepository,
        scraping_result_repository: ScrapingResultRepository,
        cache_provider: CacheProvider,
        proxy_provider: ProxyProvider,
        queue_publisher: PollingQueuePublisher,
        workers: int = 1,
    ) -> None:
        super().__init__(
            name=SCRAPING_QUEUE_NAME,
            logger=logger,
            handler=ScrapingHandler(
                logger,
                scraping_repository,
                scraping_result_repository,
                cache_provider,
                proxy_provider,
                queue_publisher,
            ),
            workers=workers,
        )


def build_scraping_event(scraping: Scraping, attempt: int = 1) -> dict[str, object]:
    """Build the versioned queue event for a Scraping."""

    return {
        "schemaVersion": SCRAPING_EVENT_SCHEMA_VERSION,
        "type": SCRAPING_EVENT_TYPE,
        "scrapingId": scraping.id,
        "createdBy": scraping.created_by,
        "idempotencyKey": scraping.idempotency_key,
        "attempt": attempt,
        "enqueuedAt": datetime.now(UTC).isoformat(),
    }


def requeue_stale_scrapings(
    scraping_repository: ScrapingRepository,
    queue_publisher: PollingQueuePublisher,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> int:
    """Republish active Scrapings left stale after an interrupted handler."""

    cutoff = (now or datetime.now(UTC)) - SCRAPING_STALE_AFTER
    stale = scraping_repository.list_stale_active(cutoff, limit)
    for scraping in stale:
        queue_publisher.publish(
            SCRAPING_QUEUE_NAME,
            build_scraping_event(scraping, attempt=max(scraping.attempts + 1, 1)),
        )
    return len(stale)


def _required_string(content: Mapping[str, Any], key: str) -> str:
    value = content.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing Scraping event field: {key}")
    return value


def _find_task(scraping: Scraping, task_id: str) -> ScrapingTask:
    task = next((item for item in scraping.tasks if item.id == task_id), None)
    if task is None:
        raise ValueError("Scraping task does not exist")
    return task


def _sanitize_error(exc: Exception, fallback: str | None = None) -> str:
    return (str(exc) or fallback or type(exc).__name__)[:500]
