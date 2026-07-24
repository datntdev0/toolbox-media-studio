"""Task-scoped Scraping queue handler tests."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.core.events.message_handler import QueueMessage
from app.domain.scraping_results import ScrapingResult
from app.domain.scrapings import (
    Scraping,
    ScrapingMetadata,
    ScrapingProgress,
    ScrapingTask,
    ScrapingTaskStatus,
)
from app.events.scraping_handler import ScrapingHandler, build_scraping_event
from app.providers.cache_provider import InMemoryCacheProvider
from app.repositories.scraping_repository import InMemoryScrapingRepository
from app.repositories.scraping_result_repository import InMemoryScrapingResultRepository


class _ProxyResult:
    html = """
    <html>
      <body>
        <h1>Chapter 1</h1>
        <div id="chaptercontent">Fresh paragraph<br>Second paragraph</div>
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


def test_handler_processes_only_the_queued_message_task() -> None:
    scrapings = InMemoryScrapingRepository()
    results = InMemoryScrapingResultRepository()
    candidate = _scraping()
    candidate.tasks.append(_task(2))
    candidate.progress = ScrapingProgress.from_tasks(candidate.tasks)
    scraping = scrapings.create_or_merge(candidate).scraping
    queued = scrapings.queue_tasks(
        scraping.id,
        scraping.created_by,
        chapter_from=1,
        chapter_to=1,
        force=False,
        etag=scraping.etag,
    )
    proxy = _Proxy()

    _handler(scrapings, results, proxy).handle(
        _message(queued.scraping, queued.tasks[0], refetch=False)
    )

    stored = scrapings.get(scraping.id, scraping.created_by)
    assert stored is not None
    assert [task.status for task in stored.tasks] == [
        ScrapingTaskStatus.COMPLETED,
        ScrapingTaskStatus.CREATED,
    ]
    assert stored.progress.completed == 1
    assert results.get(scraping.id, queued.tasks[0].id) is not None
    assert len(proxy.calls) == 1


def test_handler_skips_created_and_duplicate_completed_messages() -> None:
    scrapings = InMemoryScrapingRepository()
    results = InMemoryScrapingResultRepository()
    scraping = scrapings.create_or_merge(_scraping()).scraping
    proxy = _Proxy()
    handler = _handler(scrapings, results, proxy)

    handler.handle(_message(scraping, scraping.tasks[0], refetch=False))
    queued = scrapings.queue_tasks(
        scraping.id,
        scraping.created_by,
        chapter_from=1,
        chapter_to=1,
        force=False,
        etag=scraping.etag,
    )
    message = _message(queued.scraping, queued.tasks[0], refetch=False)
    handler.handle(message)
    handler.handle(message)

    assert len(proxy.calls) == 1
    stored = scrapings.get(scraping.id, scraping.created_by)
    assert stored is not None
    assert stored.tasks[0].attempts == 1


def test_existing_result_completes_without_fetching_when_refetch_is_false() -> None:
    scrapings = InMemoryScrapingRepository()
    results = InMemoryScrapingResultRepository()
    scraping = scrapings.create_or_merge(_scraping()).scraping
    persisted = results.upsert(_result(scraping, ["persisted"]))
    queued = scrapings.queue_tasks(
        scraping.id,
        scraping.created_by,
        chapter_from=1,
        chapter_to=1,
        force=False,
        etag=scraping.etag,
    )
    proxy = _Proxy(error=RuntimeError("must not fetch"))

    _handler(scrapings, results, proxy).handle(
        _message(queued.scraping, queued.tasks[0], refetch=False)
    )

    stored = scrapings.get(scraping.id, scraping.created_by)
    assert stored is not None
    assert stored.tasks[0].status == ScrapingTaskStatus.COMPLETED
    assert stored.tasks[0].completed_at == persisted.updated_at
    assert proxy.calls == []


def test_refetch_bypasses_existing_result_and_overwrites_content() -> None:
    scrapings = InMemoryScrapingRepository()
    results = InMemoryScrapingResultRepository()
    scraping = scrapings.create_or_merge(_scraping()).scraping
    results.upsert(_result(scraping, ["stale"]))
    queued = scrapings.queue_tasks(
        scraping.id,
        scraping.created_by,
        chapter_from=1,
        chapter_to=1,
        force=False,
        etag=scraping.etag,
    )
    proxy = _Proxy()

    _handler(scrapings, results, proxy).handle(
        _message(queued.scraping, queued.tasks[0], refetch=True)
    )

    result = results.get(scraping.id, scraping.tasks[0].id)
    assert result is not None
    assert result.content == ["Fresh paragraph", "Second paragraph"]
    assert len(proxy.calls) == 1


def test_failed_refetch_preserves_previous_result_availability() -> None:
    scrapings = InMemoryScrapingRepository()
    results = InMemoryScrapingResultRepository()
    scraping = scrapings.create_or_merge(_scraping()).scraping
    persisted = results.upsert(_result(scraping, ["persisted"]))
    scraping = scrapings.update_task(
        scraping.id,
        scraping.created_by,
        scraping.tasks[0].id,
        ScrapingTaskStatus.COMPLETED,
        attempts=1,
        error=None,
        result_available=True,
        completed_at=persisted.updated_at,
        etag=scraping.etag,
    )
    queued = scrapings.queue_tasks(
        scraping.id,
        scraping.created_by,
        chapter_from=1,
        chapter_to=1,
        force=False,
        etag=scraping.etag,
    )

    _handler(
        scrapings,
        results,
        _Proxy(error=RuntimeError("temporary")),
    ).handle(_message(queued.scraping, queued.tasks[0], refetch=True))

    stored = scrapings.get(scraping.id, scraping.created_by)
    assert stored is not None
    assert stored.tasks[0].status == ScrapingTaskStatus.FAILED
    assert stored.tasks[0].last_error == "Proxy request failed"
    assert stored.tasks[0].result_available is True
    assert stored.tasks[0].completed_at == persisted.updated_at
    assert results.get(scraping.id, scraping.tasks[0].id) is not None


def _handler(
    scrapings: InMemoryScrapingRepository,
    results: InMemoryScrapingResultRepository,
    proxy: _Proxy,
) -> ScrapingHandler:
    return ScrapingHandler(
        logger=logging.getLogger("test.scrapings"),
        scraping_repository=scrapings,
        scraping_result_repository=results,
        cache_provider=InMemoryCacheProvider(),
        proxy_provider=proxy,
    )


def _scraping() -> Scraping:
    now = datetime.now(UTC)
    task = _task(1)
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
        tasks=[task],
        progress=ScrapingProgress.from_tasks([task]),
        idempotency_key="sha256:test",
        created_by="user-1",
        created_at=now,
        updated_at=now,
    )


def _task(number: int) -> ScrapingTask:
    return ScrapingTask(
        id=f"task-{number}",
        source_url=f"https://www.novel543.com/0603625457/{number}.html",
        title=f"Chapter {number}",
        chapter_number=number,
        manifest_index=number - 1,
    )


def _result(scraping: Scraping, content: list[str]) -> ScrapingResult:
    now = datetime.now(UTC)
    task = scraping.tasks[0]
    return ScrapingResult(
        id=task.id,
        scraping_id=scraping.id,
        task_id=task.id,
        title=task.title,
        chapter_number=task.chapter_number,
        content=content,
        created_at=now,
        updated_at=now,
    )


def _message(
    scraping: Scraping,
    task: ScrapingTask,
    *,
    refetch: bool,
) -> QueueMessage:
    return QueueMessage(
        id="message-1",
        content=build_scraping_event(scraping, task, refetch=refetch),
    )
