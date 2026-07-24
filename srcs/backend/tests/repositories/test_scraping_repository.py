"""Scraping and ScrapingResult repository tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.scraping_results import ScrapingResult
from app.domain.scrapings import (
    Scraping,
    ScrapingMetadata,
    ScrapingProgress,
    ScrapingStatus,
    ScrapingTask,
    ScrapingTaskStatus,
)
from app.repositories.scraping_repository import (
    InMemoryScrapingRepository,
    ScrapingNotFoundError,
)
from app.repositories.scraping_result_repository import InMemoryScrapingResultRepository


def test_create_or_get_active_is_user_scoped_and_releases_after_terminal() -> None:
    repository = InMemoryScrapingRepository()

    first = repository.create_or_get_active(_scraping(created_by="user-1"))
    duplicate = repository.create_or_get_active(_scraping(created_by="user-1"))
    other_user = repository.create_or_get_active(_scraping(created_by="user-2"))
    repository.set_status(
        first.scraping.id,
        first.scraping.created_by,
        ScrapingStatus.COMPLETED,
    )
    after_terminal = repository.create_or_get_active(_scraping(created_by="user-1"))

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.scraping.id == first.scraping.id
    assert other_user.created is True
    assert other_user.scraping.id != first.scraping.id
    assert after_terminal.created is True
    assert after_terminal.scraping.id != first.scraping.id


def test_concurrent_create_or_get_active_creates_one_scraping() -> None:
    repository = InMemoryScrapingRepository()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: repository.create_or_get_active(_scraping()),
                range(20),
            )
        )

    assert sum(result.created for result in results) == 1
    assert len({result.scraping.id for result in results}) == 1


def test_embedded_task_update_recalculates_progress_and_reconciles() -> None:
    repository = InMemoryScrapingRepository()
    created = repository.create_or_get_active(_scraping()).scraping
    task = created.tasks[0]

    processing = repository.update_task(
        created.id,
        created.created_by,
        task.id,
        ScrapingTaskStatus.PROCESSING,
        attempts=1,
        error=None,
        result_available=False,
        completed_at=None,
        etag=created.etag,
    )
    completed_at = datetime.now(UTC)
    completed = repository.update_task(
        processing.id,
        processing.created_by,
        task.id,
        ScrapingTaskStatus.COMPLETED,
        attempts=1,
        error=None,
        result_available=True,
        completed_at=completed_at,
        etag=processing.etag,
    )
    terminal = repository.reconcile(
        completed.id,
        completed.created_by,
        etag=completed.etag,
    )

    assert completed.progress.pending == 0
    assert completed.progress.completed == 1
    assert completed.tasks[0].result_available is True
    assert terminal.status == ScrapingStatus.COMPLETED
    assert terminal.active_key == f"terminal:{terminal.id}"


def test_list_is_owned_sorted_filtered_and_paginated() -> None:
    repository = InMemoryScrapingRepository()
    first = repository.create_or_get_active(
        _scraping(created_by="user-1", key="first")
    ).scraping
    second = repository.create_or_get_active(
        _scraping(created_by="user-1", key="second")
    ).scraping
    repository.create_or_get_active(_scraping(created_by="user-2", key="third"))
    repository.set_status(
        second.id,
        second.created_by,
        ScrapingStatus.FAILED,
        error="failed",
    )

    first_page = repository.list("user-1", 1, None, None)
    second_page = repository.list(
        "user-1",
        1,
        first_page.continuation_token,
        None,
    )
    failed_page = repository.list("user-1", 10, None, ScrapingStatus.FAILED)
    all_page = repository.list(None, 10, None, None)

    assert len(first_page.items) == 1
    assert len(second_page.items) == 1
    assert {first_page.items[0].id, second_page.items[0].id} == {first.id, second.id}
    assert [item.id for item in failed_page.items] == [second.id]
    assert len(all_page.items) == 3
    assert repository.get(first.id) is not None


def test_delete_is_scoped_to_the_scraping_owner() -> None:
    repository = InMemoryScrapingRepository()
    scraping = repository.create_or_get_active(_scraping(created_by="user-1")).scraping

    with pytest.raises(ScrapingNotFoundError):
        repository.delete(scraping.id, "user-2")

    assert repository.get(scraping.id, "user-1") is not None

    repository.delete(scraping.id, "user-1")

    assert repository.get(scraping.id, "user-1") is None


def test_scraping_results_are_isolated_by_scraping_and_task() -> None:
    repository = InMemoryScrapingResultRepository()
    first = repository.upsert(_result("scraping-1", "task-1", ["first"]))
    second = repository.upsert(_result("scraping-2", "task-1", ["second"]))
    updated = repository.upsert(_result("scraping-1", "task-1", ["updated"]))

    assert first.created_at == updated.created_at
    assert repository.get("scraping-1", "task-1").content == ["updated"]  # type: ignore[union-attr]
    assert repository.get("scraping-2", "task-1").content == ["second"]  # type: ignore[union-attr]
    assert second.scraping_id != updated.scraping_id


def test_delete_scraping_results_removes_only_the_requested_partition() -> None:
    repository = InMemoryScrapingResultRepository()
    repository.upsert(_result("scraping-1", "task-1", ["first"]))
    repository.upsert(_result("scraping-1", "task-2", ["second"]))
    repository.upsert(_result("scraping-2", "task-1", ["other"]))

    repository.delete_by_scraping("scraping-1")

    assert repository.get("scraping-1", "task-1") is None
    assert repository.get("scraping-1", "task-2") is None
    assert repository.get("scraping-2", "task-1") is not None


def _scraping(
    *,
    created_by: str = "user-1",
    key: str = "default",
) -> Scraping:
    now = datetime.now(UTC)
    task = ScrapingTask(
        id="task-1",
        source_url="https://www.novel543.com/0603625457/1.html",
        title="Chapter 1",
        chapter_number=1,
        manifest_index=0,
    )
    idempotency_key = f"sha256:{key}"
    return Scraping(
        id=str(uuid4()),
        crawler_id="novel543",
        source_url="https://www.novel543.com/0603625457/dir",
        metadata=ScrapingMetadata(
            source_novel_id="0603625457",
            title="Novel",
            author="Author",
            category="Fantasy",
            updated_date="2026-07-23",
            protagonists=[],
            description="Description",
            cover_image_url=None,
            fetched_at=now,
        ),
        status=ScrapingStatus.QUEUED,
        tasks=[task],
        progress=ScrapingProgress.from_tasks([task]),
        attempts=0,
        last_error=None,
        idempotency_key=idempotency_key,
        active_key=idempotency_key,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


def _result(scraping_id: str, task_id: str, content: list[str]) -> ScrapingResult:
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
