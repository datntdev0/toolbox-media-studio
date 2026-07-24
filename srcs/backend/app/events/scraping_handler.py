"""Queue handler and listener for task-scoped Scraping events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from logging import Logger
from typing import Any

from app.core.events.message_handler import MessageHandler, QueueMessage
from app.core.events.polling_queue_subscriber import PollingQueueSubscriber
from app.core.realtime import RealtimeHub
from app.domain.scraping_results import ScrapingResult
from app.domain.scrapings import Scraping, ScrapingTask, ScrapingTaskStatus
from app.providers.cache_provider import CacheProvider
from app.providers.crawler_provider import fetch_chapter_content
from app.providers.proxy_service_provider import ProxyProvider
from app.repositories.scraping_repository import (
    ScrapingConflictError,
    ScrapingNotFoundError,
    ScrapingRepository,
)
from app.repositories.scraping_result_repository import ScrapingResultRepository

SCRAPING_QUEUE_NAME = "scrapings"
SCRAPING_EVENT_TYPE = "scraping.task.requested"
SCRAPING_EVENT_SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class ScrapingEvent:
    """Validated task-scoped Scraping queue event."""

    scraping_id: str
    created_by: str
    idempotency_key: str
    task_id: str
    refetch: bool
    enqueued_at: str

    @classmethod
    def from_mapping(cls, content: Mapping[str, Any]) -> ScrapingEvent:
        if content.get("schemaVersion") != SCRAPING_EVENT_SCHEMA_VERSION:
            raise ValueError("Unsupported Scraping event schema")
        if content.get("type") != SCRAPING_EVENT_TYPE:
            raise ValueError("Unsupported Scraping event type")
        refetch = content.get("refetch", False)
        if not isinstance(refetch, bool):
            raise ValueError("Invalid Scraping event refetch flag")
        return cls(
            scraping_id=_required_string(content, "scrapingId"),
            created_by=_required_string(content, "createdBy"),
            idempotency_key=_required_string(content, "idempotencyKey"),
            task_id=_required_string(content, "taskId"),
            refetch=refetch,
            enqueued_at=_required_string(content, "enqueuedAt"),
        )


class ScrapingHandler(MessageHandler):
    """Processes one queued chapter task and persists its isolated result."""

    def __init__(
        self,
        logger: Logger,
        scraping_repository: ScrapingRepository,
        scraping_result_repository: ScrapingResultRepository,
        cache_provider: CacheProvider,
        proxy_provider: ProxyProvider,
        realtime_hub: RealtimeHub | None = None,
    ) -> None:
        self._logger = logger
        self._scrapings = scraping_repository
        self._results = scraping_result_repository
        self._cache = cache_provider
        self._proxy = proxy_provider
        self._realtime = realtime_hub

    def handle(self, message: QueueMessage) -> None:
        if message.content is None:
            raise ValueError("Scraping queue message has no content")
        event = ScrapingEvent.from_mapping(message.content)
        scraping = self._scrapings.get(event.scraping_id, event.created_by)
        if scraping is None or scraping.idempotency_key != event.idempotency_key:
            return
        task = _find_task(scraping, event.task_id)
        if task is None or task.status != ScrapingTaskStatus.QUEUED:
            return

        claimed = self._claim_task_with_retry(scraping, task.id)
        if claimed is None:
            return
        task = _require_task(claimed, task.id)
        self._publish_update(claimed, task_id=task.id)
        self._logger.info(
            "Processing Scraping task: %s",
            {
                "messageId": message.id,
                "scrapingId": claimed.id,
                "taskId": task.id,
                "createdBy": claimed.created_by,
                "attempt": task.attempts,
                "refetch": event.refetch,
            },
        )

        existing = self._results.get(claimed.id, task.id)
        try:
            if existing is not None and not event.refetch:
                completed = self._update_task_with_retry(
                    claimed,
                    task.id,
                    ScrapingTaskStatus.COMPLETED,
                    attempts=task.attempts,
                    error=None,
                    result_available=True,
                    completed_at=existing.updated_at,
                )
            else:
                chapter = fetch_chapter_content(
                    crawler_id=claimed.crawler_id,
                    chapter_url=task.source_url,
                    cache_provider=self._cache,
                    proxy_provider=self._proxy,
                    use_cache=not event.refetch,
                )
                now = datetime.now(UTC)
                result = self._results.upsert(
                    ScrapingResult(
                        id=task.id,
                        scraping_id=claimed.id,
                        task_id=task.id,
                        title=chapter.chapter_title,
                        chapter_number=chapter.chapter_number,
                        content=chapter.content,
                        created_at=now,
                        updated_at=now,
                    )
                )
                completed = self._update_task_with_retry(
                    claimed,
                    task.id,
                    ScrapingTaskStatus.COMPLETED,
                    attempts=task.attempts,
                    error=None,
                    result_available=True,
                    completed_at=result.updated_at,
                )
            self._logger.info(
                "Scraping task completed %s",
                {
                    "messageId": message.id,
                    "scrapingId": completed.id,
                    "taskId": task.id,
                },
            )
        except Exception as exc:
            latest = self._scrapings.get(claimed.id, claimed.created_by) or claimed
            latest_task = _find_task(latest, task.id) or task
            preserved_result = self._results.get(claimed.id, task.id)
            self._update_task_with_retry(
                latest,
                task.id,
                ScrapingTaskStatus.FAILED,
                attempts=latest_task.attempts,
                error=_sanitize_error(exc),
                result_available=(
                    latest_task.result_available or preserved_result is not None
                ),
                completed_at=(
                    latest_task.completed_at
                    or (preserved_result.updated_at if preserved_result is not None else None)
                ),
            )

    def _claim_task_with_retry(
        self,
        scraping: Scraping,
        task_id: str,
    ) -> Scraping | None:
        for _ in range(3):
            try:
                return self._scrapings.claim_task(
                    scraping.id,
                    scraping.created_by,
                    task_id,
                    etag=scraping.etag,
                )
            except ScrapingConflictError:
                latest = self._scrapings.get(scraping.id, scraping.created_by)
                if latest is None:
                    return None
                task = _find_task(latest, task_id)
                if task is None or task.status != ScrapingTaskStatus.QUEUED:
                    return None
                scraping = latest
            except ScrapingNotFoundError:
                return None
        raise ScrapingConflictError("Scraping task claim conflicted repeatedly")

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
                updated = self._scrapings.update_task(
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
                self._publish_update(updated, task_id=task_id)
                return updated
            except ScrapingConflictError:
                latest = self._scrapings.get(scraping.id, scraping.created_by)
                if latest is None:
                    raise ScrapingNotFoundError from None
                scraping = latest
        raise ScrapingConflictError("Scraping task update conflicted repeatedly")

    def _publish_update(self, scraping: Scraping, task_id: str | None = None) -> None:
        if self._realtime is None:
            return
        self._realtime.publish(
            "scraping.updated",
            build_scraping_updated_payload(scraping, task_id=task_id),
        )


class ScrapingQueueListener(PollingQueueSubscriber):
    """Queue listener configured with a task-scoped ScrapingHandler."""

    def __init__(
        self,
        logger: Logger,
        scraping_repository: ScrapingRepository,
        scraping_result_repository: ScrapingResultRepository,
        cache_provider: CacheProvider,
        proxy_provider: ProxyProvider,
        realtime_hub: RealtimeHub | None = None,
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
                realtime_hub,
            ),
            workers=workers,
        )


def build_scraping_event(
    scraping: Scraping,
    task: ScrapingTask,
    *,
    refetch: bool,
) -> dict[str, object]:
    """Build one versioned queue event for a Scraping task."""

    return {
        "schemaVersion": SCRAPING_EVENT_SCHEMA_VERSION,
        "type": SCRAPING_EVENT_TYPE,
        "scrapingId": scraping.id,
        "createdBy": scraping.created_by,
        "idempotencyKey": scraping.idempotency_key,
        "taskId": task.id,
        "refetch": refetch,
        "enqueuedAt": datetime.now(UTC).isoformat(),
    }


def build_scraping_updated_payload(
    scraping: Scraping,
    *,
    task_id: str | None = None,
) -> dict[str, object]:
    """Build the lightweight UI invalidation event sent over WebSockets."""

    payload: dict[str, object] = {
        "scrapingId": scraping.id,
        "updatedAt": scraping.updated_at.isoformat(),
        "progress": {
            "total": scraping.progress.total,
            "created": scraping.progress.created,
            "queued": scraping.progress.queued,
            "running": scraping.progress.running,
            "completed": scraping.progress.completed,
            "failed": scraping.progress.failed,
        },
    }
    if task_id is not None:
        payload["taskId"] = task_id
    return payload


def _required_string(content: Mapping[str, Any], key: str) -> str:
    value = content.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing Scraping event field: {key}")
    return value


def _find_task(scraping: Scraping, task_id: str) -> ScrapingTask | None:
    return next((item for item in scraping.tasks if item.id == task_id), None)


def _require_task(scraping: Scraping, task_id: str) -> ScrapingTask:
    task = _find_task(scraping, task_id)
    if task is None:
        raise ScrapingNotFoundError
    return task


def _sanitize_error(exc: Exception) -> str:
    return (str(exc) or type(exc).__name__)[:500]
