"""Reusable scheduled queue consumer infrastructure."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Event
from typing import Any, Protocol

from apscheduler.executors.pool import ThreadPoolExecutor  # type: ignore[import-untyped]
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]

from app.core.logging import get_logger
from app.providers.queue_provider import QueueProvider, ReceivedQueueMessage

logger = get_logger("queue_consumer")


class QueueMessageHandler(Protocol):
    """Process one received message."""

    def handle(self, message: ReceivedQueueMessage) -> None: ...


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Queue visibility retry delays."""

    delays: tuple[int, ...] = (2, 4, 8, 16, 32)

    def delay_for(self, dequeue_count: int) -> int | None:
        if dequeue_count < 1:
            dequeue_count = 1
        index = dequeue_count - 1
        if index >= len(self.delays):
            return None
        return self.delays[index]


class ScheduledQueueConsumer:
    """APScheduler-backed queue consumer with competing serial slots."""

    def __init__(
        self,
        *,
        name: str,
        source_queue: QueueProvider,
        dead_letter_queue: QueueProvider,
        handler: QueueMessageHandler,
        retry_policy: RetryPolicy,
        consumer_count: int,
        poll_interval_seconds: int,
        visibility_timeout_seconds: int,
        scheduler: BackgroundScheduler | None = None,
    ) -> None:
        if consumer_count < 1:
            raise ValueError("consumer_count must be positive")
        self._name = name
        self._source_queue = source_queue
        self._dead_letter_queue = dead_letter_queue
        self._handler = handler
        self._retry_policy = retry_policy
        self._consumer_count = consumer_count
        self._poll_interval_seconds = poll_interval_seconds
        self._visibility_timeout_seconds = visibility_timeout_seconds
        self._stop_event = Event()
        self._scheduler = scheduler or BackgroundScheduler(
            executors={"default": ThreadPoolExecutor(max_workers=consumer_count)}
        )

    def start(self) -> None:
        self._stop_event.clear()
        for slot in range(self._consumer_count):
            self._schedule_slot(slot, delay_seconds=0)
        self._scheduler.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._scheduler.running:
            self._scheduler.shutdown(wait=True)

    def _drain_slot(self, slot: int) -> None:
        consumer_id = f"{self._name}-{slot}"
        try:
            while not self._stop_event.is_set():
                message = self._source_queue.receive_one(self._visibility_timeout_seconds)
                if message is None:
                    return
                self._process_message(message, consumer_id)
        finally:
            if not self._stop_event.is_set():
                self._schedule_slot(slot, delay_seconds=self._poll_interval_seconds)

    def _schedule_slot(self, slot: int, delay_seconds: int) -> None:
        self._scheduler.add_job(
            self._drain_slot,
            "date",
            run_date=datetime.now(UTC) + timedelta(seconds=delay_seconds),
            args=[slot],
            id=f"{self._name}-{slot}",
            replace_existing=True,
        )

    def _process_message(self, message: ReceivedQueueMessage, consumer_id: str) -> None:
        attempt = max(message.dequeue_count, 1)
        logger.info(
            "Processing queue message",
            extra={
                "queueName": self._source_queue.queue_name,
                "messageId": message.id,
                "attempt": attempt,
                "consumerId": consumer_id,
                "outcome": "processing",
            },
        )

        try:
            self._handler.handle(message)
        except Exception as exc:
            delay = self._retry_policy.delay_for(attempt)
            error = _sanitize_error(exc)
            if delay is None:
                self._dead_letter(message, attempt, error)
                return
            self._source_queue.retry(message, visibility_timeout=delay)
            logger.info(
                "Queue message scheduled for retry",
                extra={
                    "queueName": self._source_queue.queue_name,
                    "messageId": message.id,
                    "attempt": attempt,
                    "consumerId": consumer_id,
                    "outcome": "retrying",
                },
            )
            return

        self._source_queue.delete(message)
        logger.info(
            "Queue message processed successfully",
            extra={
                "queueName": self._source_queue.queue_name,
                "messageId": message.id,
                "attempt": attempt,
                "consumerId": consumer_id,
                "outcome": "completed",
            },
        )

    def _dead_letter(self, message: ReceivedQueueMessage, attempt: int, error: str) -> None:
        envelope: Mapping[str, Any] = {
            "schemaVersion": 1,
            "sourceQueue": self._source_queue.queue_name,
            "sourceMessageId": message.id,
            "dequeueCount": attempt,
            "failedAt": datetime.now(UTC).isoformat(),
            "errorMessage": error,
            "message": dict(message.content),
        }
        self._dead_letter_queue.send(envelope)
        mark_failed = getattr(self._handler, "mark_failed", None)
        if callable(mark_failed):
            mark_failed(message, error)
        self._source_queue.delete(message)
        logger.info(
            "Queue message dead-lettered",
            extra={
                "queueName": self._source_queue.queue_name,
                "messageId": message.id,
                "attempt": attempt,
                "consumerId": self._name,
                "outcome": "failed",
            },
        )


def _sanitize_error(exc: Exception) -> str:
    message = str(exc) or type(exc).__name__
    return message[:500]
