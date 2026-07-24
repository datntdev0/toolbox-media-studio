"""Scraping and ScrapingResult repository tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from app.domain.scraping_results import ScrapingResult
from app.domain.scrapings import (
    Scraping,
    ScrapingMetadata,
    ScrapingProgress,
    ScrapingTask,
    ScrapingTaskStatus,
)
from app.repositories.scraping_repository import (
    InMemoryScrapingRepository,
    ScrapingChapterRangeError,
    ScrapingNotFoundError,
)
from app.repositories.scraping_result_repository import InMemoryScrapingResultRepository


def test_create_or_merge_is_permanent_and_preserves_existing_task_state() -> None:
    repository = InMemoryScrapingRepository()
    original = repository.create_or_merge(_scraping()).scraping
    completed_at = datetime.now(UTC)
    original = repository.update_task(
        original.id,
        original.created_by,
        original.tasks[0].id,
        ScrapingTaskStatus.COMPLETED,
        attempts=1,
        error=None,
        result_available=True,
        completed_at=completed_at,
        etag=original.etag,
    )

    candidate = _scraping(title="Refreshed Novel")
    candidate.tasks[0].title = "Refreshed Chapter 1"
    candidate.tasks.append(_task(2))
    candidate.progress = ScrapingProgress.from_tasks(candidate.tasks)
    merged = repository.create_or_merge(candidate)

    assert merged.created is False
    assert merged.scraping.id == original.id
    assert merged.scraping.metadata.title == "Refreshed Novel"
    assert [task.title for task in merged.scraping.tasks] == [
        "Refreshed Chapter 1",
        "Chapter 2",
    ]
    assert [task.status for task in merged.scraping.tasks] == [
        ScrapingTaskStatus.COMPLETED,
        ScrapingTaskStatus.CREATED,
    ]
    assert merged.scraping.tasks[0].completed_at == completed_at


def test_concurrent_create_or_merge_creates_one_scraping() -> None:
    repository = InMemoryScrapingRepository()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: repository.create_or_merge(_scraping()),
                range(24),
            )
        )

    assert sum(result.created for result in results) == 1
    assert len({result.scraping.id for result in results}) == 1


def test_queue_claim_stop_and_progress_are_task_scoped() -> None:
    repository = InMemoryScrapingRepository()
    candidate = _scraping()
    candidate.tasks.append(_task(2))
    candidate.progress = ScrapingProgress.from_tasks(candidate.tasks)
    scraping = repository.create_or_merge(candidate).scraping

    queued = repository.queue_tasks(
        scraping.id,
        scraping.created_by,
        chapter_from=1,
        chapter_to=2,
        force=False,
        etag=scraping.etag,
    )
    assert len(queued.tasks) == 2
    assert queued.scraping.progress.queued == 2

    claimed = repository.claim_task(
        scraping.id,
        scraping.created_by,
        queued.tasks[0].id,
        etag=queued.scraping.etag,
    )
    assert claimed is not None
    assert claimed.progress.running == 1
    assert claimed.progress.queued == 1
    assert claimed.tasks[0].attempts == 1
    assert repository.claim_task(
        scraping.id,
        scraping.created_by,
        queued.tasks[0].id,
        etag=claimed.etag,
    ) is None

    stopped = repository.stop_queued_tasks(
        scraping.id,
        scraping.created_by,
        etag=claimed.etag,
    )
    assert [task.status for task in stopped.tasks] == [
        ScrapingTaskStatus.RUNNING,
        ScrapingTaskStatus.CREATED,
    ]
    assert stopped.progress.running == 1
    assert stopped.progress.created == 1


def test_force_requeues_active_tasks_and_missing_range_is_rejected() -> None:
    repository = InMemoryScrapingRepository()
    scraping = repository.create_or_merge(_scraping()).scraping
    queued = repository.queue_tasks(
        scraping.id,
        scraping.created_by,
        chapter_from=1,
        chapter_to=1,
        force=False,
        etag=scraping.etag,
    )
    claimed = repository.claim_task(
        scraping.id,
        scraping.created_by,
        queued.tasks[0].id,
        etag=queued.scraping.etag,
    )
    assert claimed is not None

    forced = repository.queue_tasks(
        scraping.id,
        scraping.created_by,
        chapter_from=1,
        chapter_to=1,
        force=True,
        etag=claimed.etag,
    )
    assert [task.status for task in forced.tasks] == [ScrapingTaskStatus.QUEUED]
    assert forced.scraping.tasks[0].attempts == 1

    with pytest.raises(ScrapingChapterRangeError):
        repository.queue_tasks(
            scraping.id,
            scraping.created_by,
            chapter_from=99,
            chapter_to=100,
            force=False,
            etag=forced.scraping.etag,
        )


def test_list_is_sorted_and_paginated_without_status_filter() -> None:
    repository = InMemoryScrapingRepository()
    first = repository.create_or_merge(_scraping(key="one")).scraping
    second = repository.create_or_merge(_scraping(key="two")).scraping

    page = repository.list(None, 1, None)
    assert page.items[0].id == second.id
    assert page.continuation_token == "1"
    final = repository.list(None, 1, page.continuation_token)
    assert final.items[0].id == first.id
    assert final.continuation_token is None


def test_delete_is_scoped_to_the_scraping_owner() -> None:
    repository = InMemoryScrapingRepository()
    scraping = repository.create_or_merge(_scraping()).scraping

    with pytest.raises(ScrapingNotFoundError):
        repository.delete(scraping.id, "other-user")
    repository.delete(scraping.id, scraping.created_by)
    assert repository.get(scraping.id, scraping.created_by) is None


def test_scraping_results_are_isolated_and_upsert_preserves_created_at() -> None:
    repository = InMemoryScrapingResultRepository()
    first = repository.upsert(_result("scraping-1", "task-1", ["first"]))
    replacement = repository.upsert(
        _result("scraping-1", "task-1", ["replacement"])
    )
    repository.upsert(_result("scraping-2", "task-1", ["other"]))

    assert replacement.created_at == first.created_at
    assert repository.get("scraping-1", "task-1").content == ["replacement"]  # type: ignore[union-attr]
    assert repository.get("scraping-2", "task-1").content == ["other"]  # type: ignore[union-attr]

    repository.delete_by_scraping("scraping-1")
    assert repository.get("scraping-1", "task-1") is None
    assert repository.get("scraping-2", "task-1") is not None


def _scraping(*, key: str = "test", title: str = "Novel") -> Scraping:
    now = datetime.now(UTC)
    task = _task(1)
    idempotency_key = f"sha256:{key}"
    return Scraping(
        id=f"scraping-{key}",
        crawler_id="novel543",
        source_url=f"https://www.novel543.com/{key}/dir",
        metadata=ScrapingMetadata(
            source_novel_id=key,
            title=title,
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
        idempotency_key=idempotency_key,
        created_by="user-1",
        created_at=now,
        updated_at=now,
    )


def _task(chapter_number: int) -> ScrapingTask:
    return ScrapingTask(
        id=f"task-{chapter_number}",
        source_url=f"https://www.novel543.com/test/{chapter_number}.html",
        title=f"Chapter {chapter_number}",
        chapter_number=chapter_number,
        manifest_index=chapter_number - 1,
    )


def _result(
    scraping_id: str,
    task_id: str,
    content: list[str],
) -> ScrapingResult:
    now = datetime.now(UTC)
    return ScrapingResult(
        id=task_id,
        scraping_id=scraping_id,
        task_id=task_id,
        title="Chapter",
        chapter_number=1,
        content=content,
        created_at=now,
        updated_at=now,
    )
