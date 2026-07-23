"""Scraping queue handler tests."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.core.events.message_handler import QueueMessage
from app.domain.scraping_results import ScrapingResult
from app.domain.scrapings import (
    Scraping,
    ScrapingMetadata,
    ScrapingProgress,
    ScrapingStatus,
    ScrapingTask,
    ScrapingTaskStatus,
)
from app.events.scraping_handler import (
    SCRAPING_QUEUE_NAME,
    ScrapingHandler,
    build_scraping_event,
)
from app.providers.cache_provider import InMemoryCacheProvider
from app.repositories.scraping_repository import InMemoryScrapingRepository
from app.repositories.scraping_result_repository import InMemoryScrapingResultRepository


class _ProxyResult:
    html = """
    <html>
      <body>
        <h1>Chapter 1</h1>
        <div id="chaptercontent">First paragraph<br>Second paragraph</div>
      </body>
    </html>
    """


class _Proxy:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[str] = []

    def get(self, url: str) -> _ProxyResult:
        self.calls.append(url)
        if self.error is not None:
            raise self.error
        return _ProxyResult()


class _Publisher:
    def __init__(self) -> None:
        self.messages: list[tuple[str, Mapping[str, Any]]] = []

    def publish(self, queue_name: str, message: Mapping[str, Any]) -> None:
        self.messages.append((queue_name, dict(message)))


def test_handler_persists_result_before_completing_scraping() -> None:
    scrapings = InMemoryScrapingRepository()
    results = InMemoryScrapingResultRepository()
    scraping = scrapings.create_or_get_active(_scraping()).scraping
    proxy = _Proxy()
    handler = _handler(scrapings, results, proxy, _Publisher())

    handler.handle(_message(scraping))

    stored = scrapings.get(scraping.id, scraping.created_by)
    result = results.get(scraping.id, scraping.tasks[0].id)
    assert stored is not None
    assert result is not None
    assert stored.status == ScrapingStatus.COMPLETED
    assert stored.tasks[0].status == ScrapingTaskStatus.COMPLETED
    assert stored.tasks[0].result_available is True
    assert result.content == ["First paragraph", "Second paragraph"]


def test_existing_result_repairs_task_without_fetching_again() -> None:
    scrapings = InMemoryScrapingRepository()
    results = InMemoryScrapingResultRepository()
    scraping = scrapings.create_or_get_active(_scraping()).scraping
    now = datetime.now(UTC)
    results.upsert(
        ScrapingResult(
            id=scraping.tasks[0].id,
            scraping_id=scraping.id,
            task_id=scraping.tasks[0].id,
            title="Chapter 1",
            chapter_number=1,
            content=["persisted"],
            created_at=now,
            updated_at=now,
        )
    )
    proxy = _Proxy(error=RuntimeError("must not fetch"))
    handler = _handler(scrapings, results, proxy, _Publisher())

    handler.handle(_message(scraping))

    stored = scrapings.get(scraping.id, scraping.created_by)
    assert stored is not None
    assert stored.status == ScrapingStatus.COMPLETED
    assert stored.tasks[0].result_available is True
    assert proxy.calls == []


def test_transient_failure_marks_retrying_and_republishes() -> None:
    scrapings = InMemoryScrapingRepository()
    results = InMemoryScrapingResultRepository()
    scraping = scrapings.create_or_get_active(_scraping()).scraping
    publisher = _Publisher()
    handler = _handler(
        scrapings,
        results,
        _Proxy(error=RuntimeError("temporary")),
        publisher,
        max_attempts=3,
    )

    handler.handle(_message(scraping))

    stored = scrapings.get(scraping.id, scraping.created_by)
    assert stored is not None
    assert stored.status == ScrapingStatus.RETRYING
    assert stored.tasks[0].status == ScrapingTaskStatus.RETRYING
    assert publisher.messages[0][0] == SCRAPING_QUEUE_NAME
    assert publisher.messages[0][1]["attempt"] == 2


def test_exhausted_failure_marks_scraping_failed_without_republish() -> None:
    scrapings = InMemoryScrapingRepository()
    results = InMemoryScrapingResultRepository()
    scraping = scrapings.create_or_get_active(_scraping()).scraping
    publisher = _Publisher()
    handler = _handler(
        scrapings,
        results,
        _Proxy(error=RuntimeError("permanent")),
        publisher,
        max_attempts=1,
    )

    handler.handle(_message(scraping))

    stored = scrapings.get(scraping.id, scraping.created_by)
    assert stored is not None
    assert stored.status == ScrapingStatus.FAILED
    assert stored.tasks[0].status == ScrapingTaskStatus.FAILED
    assert publisher.messages == []


def test_failed_task_does_not_abandon_another_retryable_task() -> None:
    scrapings = InMemoryScrapingRepository()
    results = InMemoryScrapingResultRepository()
    candidate = _scraping()
    candidate.tasks.append(
        ScrapingTask(
            id="task-2",
            source_url="https://www.novel543.com/0603625457/2.html",
            title="Chapter 2",
            chapter_number=2,
            manifest_index=1,
            attempts=1,
        )
    )
    candidate.progress = ScrapingProgress.from_tasks(candidate.tasks)
    scraping = scrapings.create_or_get_active(candidate).scraping
    publisher = _Publisher()
    handler = _handler(
        scrapings,
        results,
        _Proxy(error=RuntimeError("temporary")),
        publisher,
        max_attempts=2,
    )

    handler.handle(_message(scraping))

    stored = scrapings.get(scraping.id, scraping.created_by)
    assert stored is not None
    assert stored.status == ScrapingStatus.RETRYING
    assert [task.status for task in stored.tasks] == [
        ScrapingTaskStatus.RETRYING,
        ScrapingTaskStatus.FAILED,
    ]
    assert len(publisher.messages) == 1


def _handler(
    scrapings: InMemoryScrapingRepository,
    results: InMemoryScrapingResultRepository,
    proxy: _Proxy,
    publisher: _Publisher,
    *,
    max_attempts: int = 3,
) -> ScrapingHandler:
    return ScrapingHandler(
        logger=logging.getLogger("test.scrapings"),
        scraping_repository=scrapings,
        scraping_result_repository=results,
        cache_provider=InMemoryCacheProvider(),
        proxy_provider=proxy,
        queue_publisher=publisher,
        max_attempts=max_attempts,
    )


def _scraping() -> Scraping:
    now = datetime.now(UTC)
    task = ScrapingTask(
        id="task-1",
        source_url="https://www.novel543.com/0603625457/1.html",
        title="Chapter 1",
        chapter_number=1,
        manifest_index=0,
    )
    return Scraping(
        id="scraping-1",
        crawler_id="novel543",
        source_url="https://www.novel543.com/0603625457/dir",
        metadata=ScrapingMetadata(
            source_novel_id="0603625457",
            title="Novel",
            author=None,
            category=None,
            updated_date=None,
            protagonists=[],
            description=None,
            cover_image_url=None,
            fetched_at=now,
        ),
        status=ScrapingStatus.QUEUED,
        tasks=[task],
        progress=ScrapingProgress.from_tasks([task]),
        attempts=0,
        last_error=None,
        idempotency_key="sha256:test",
        active_key="sha256:test",
        created_by="user-1",
        created_at=now,
        updated_at=now,
    )


def _message(scraping: Scraping) -> QueueMessage:
    return QueueMessage(
        id="message-1",
        content=build_scraping_event(scraping),
    )
