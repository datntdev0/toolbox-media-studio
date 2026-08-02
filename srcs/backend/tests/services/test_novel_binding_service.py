"""Novel binding and synchronization behavior tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.novels import Novel
from app.domain.scraping_results import ScrapingResult
from app.domain.scrapings import (
    Scraping,
    ScrapingMetadata,
    ScrapingProgress,
    ScrapingTask,
    ScrapingTaskStatus,
)
from app.repositories.novel_chapter_repository import InMemoryNovelChapterRepository
from app.repositories.novel_repository import InMemoryNovelRepository
from app.repositories.scraping_repository import ScrapingNotFoundError
from app.services.novel_binding_service import (
    NovelBindingConcurrencyError,
    NovelBindingConflictError,
    NovelBindingService,
)


class MutableScrapingRepository:
    def __init__(self, scraping: Scraping) -> None:
        self.scraping = scraping

    def get_by_id(self, id: str, created_by: str | None = None) -> Scraping:
        del created_by
        if id != self.scraping.id:
            raise ScrapingNotFoundError()
        return self.scraping


class MutableResultRepository:
    def __init__(self, results: list[ScrapingResult]) -> None:
        self.results = {
            (result.scraping_id, result.task_id): result for result in results
        }

    def get(self, scraping_id: str, task_id: str) -> ScrapingResult | None:
        return self.results.get((scraping_id, task_id))


def test_bind_clones_manifest_order_and_only_available_content() -> None:
    service, novels, chapters, scraping_source, _ = _service(
        tasks=[
            _task("third", 2, result_available=True),
            _task("first", 0, result_available=True),
            _task("second", 1, result_available=False),
        ],
        results=[
            _result("third", ["Third"]),
            _result("first", ["First line", "Second line"]),
        ],
    )

    result = service.bind("novel-1", "scraping-1", updated_by="member-2")

    assert result.added == 3
    assert (result.refreshed, result.preserved, result.removed) == (0, 0, 0)
    assert [chapter.id for chapter in result.chapters] == [
        "first",
        "second",
        "third",
    ]
    assert result.novel.chapter_count == 3
    assert result.novel.binding is not None
    assert result.novel.binding.scraping_id == scraping_source.scraping.id
    assert result.novel.updated_by == "member-2"

    first = chapters.get("novel-1", "first")
    second = chapters.get("novel-1", "second")
    assert first is not None
    assert first.content == ["First line", "Second line"]
    assert second is not None
    assert second.content_available is False
    assert second.content == []
    assert novels.get_by_id("novel-1").chapter_count == 3  # type: ignore[union-attr]


def test_bind_rejects_a_bound_or_nonempty_novel() -> None:
    service, _, _, _, _ = _service(tasks=[_task("one", 0)], results=[])
    service.bind("novel-1", "scraping-1", updated_by="user-1")

    with pytest.raises(NovelBindingConflictError):
        service.bind("novel-1", "scraping-1", updated_by="user-1")

    service, novels, chapters, _, _ = _service(
        tasks=[_task("one", 0)],
        results=[],
    )
    novel = novels.get_by_id("novel-1")
    assert novel is not None
    novel.chapter_count = 1
    novels.update(novel, novel.etag)

    with pytest.raises(NovelBindingConflictError):
        service.bind("novel-1", "scraping-1", updated_by="user-1")
    assert chapters.list("novel-1").items == []


def test_sync_adds_refreshes_preserves_edits_and_marks_removed_chapters() -> None:
    old = datetime.now(UTC) - timedelta(hours=1)
    service, _, chapters, scraping_source, results = _service(
        tasks=[
            _task("refresh", 0, result_available=True),
            _task("edited", 1, result_available=True),
            _task("removed", 2, result_available=True),
            _task("newly-available", 3, result_available=False),
        ],
        results=[
            _result("refresh", ["Old refresh"], updated_at=old),
            _result("edited", ["Old edited"], updated_at=old),
            _result("removed", ["Old removed"], updated_at=old),
        ],
    )
    service.bind("novel-1", "scraping-1", updated_by="owner")
    edited = chapters.get("novel-1", "edited")
    assert edited is not None and edited.etag is not None
    service.update_chapter_content(
        "novel-1",
        "edited",
        "Manual first\n\nManual second",
        etag=edited.etag,
    )

    newer = datetime.now(UTC) + timedelta(hours=1)
    results.results[("scraping-1", "refresh")] = _result(
        "refresh",
        ["Fresh refresh"],
        updated_at=newer,
    )
    results.results[("scraping-1", "edited")] = _result(
        "edited",
        ["Source edited"],
        updated_at=newer,
    )
    results.results[("scraping-1", "newly-available")] = _result(
        "newly-available",
        ["Now downloaded"],
        updated_at=newer,
    )
    results.results[("scraping-1", "added")] = _result(
        "added",
        ["Brand new"],
        updated_at=newer,
    )
    scraping_source.scraping.tasks = [
        _task("refresh", 0, result_available=True),
        _task("edited", 1, result_available=True),
        _task("newly-available", 2, result_available=True),
        _task("added", 3, result_available=True),
    ]
    scraping_source.scraping.progress = ScrapingProgress.from_tasks(
        scraping_source.scraping.tasks
    )
    scraping_source.scraping.updated_at = newer

    synced = service.sync("novel-1", updated_by="member-2")

    assert (synced.added, synced.refreshed, synced.preserved, synced.removed) == (
        1,
        2,
        1,
        1,
    )
    by_id = {chapter.id: chapter for chapter in synced.chapters}
    assert by_id["removed"].source_removed is True
    assert by_id["edited"].manually_edited is True
    assert by_id["edited"].source_updated is True
    assert by_id["newly-available"].content_available is True

    _, edited_content = service.get_chapter_content("novel-1", "edited")
    _, refreshed_content = service.get_chapter_content("novel-1", "refresh")
    _, newly_available_content = service.get_chapter_content(
        "novel-1",
        "newly-available",
    )
    assert edited_content == ["Manual first", "Manual second"]
    assert refreshed_content == ["Fresh refresh"]
    assert newly_available_content == ["Now downloaded"]
    assert by_id["added"].content == ["Brand new"]


def test_chapter_edit_requires_current_etag_and_marks_manual_content() -> None:
    service, _, chapters, _, _ = _service(
        tasks=[_task("chapter-1", 0, result_available=True)],
        results=[_result("chapter-1", ["Original"])],
    )
    service.bind("novel-1", "scraping-1", updated_by="owner")
    chapter = chapters.get("novel-1", "chapter-1")
    assert chapter is not None and chapter.etag is not None

    updated, paragraphs = service.update_chapter_content(
        "novel-1",
        "chapter-1",
        "Edited one\n\nEdited two",
        etag=chapter.etag,
    )

    assert paragraphs == ["Edited one", "Edited two"]
    assert updated.manually_edited is True
    assert service.get_chapter_content("novel-1", "chapter-1")[1] == paragraphs
    with pytest.raises(NovelBindingConcurrencyError):
        service.update_chapter_content(
            "novel-1",
            "chapter-1",
            "Stale edit",
            etag=chapter.etag,
        )


def _service(
    *,
    tasks: list[ScrapingTask],
    results: list[ScrapingResult],
) -> tuple[
    NovelBindingService,
    InMemoryNovelRepository,
    InMemoryNovelChapterRepository,
    MutableScrapingRepository,
    MutableResultRepository,
]:
    novels = InMemoryNovelRepository()
    chapters = InMemoryNovelChapterRepository()
    scraping_source = MutableScrapingRepository(_scraping(tasks))
    result_source = MutableResultRepository(results)
    novels.create(_novel())
    service = NovelBindingService(
        novels,
        scraping_source,  # type: ignore[arg-type]
        result_source,  # type: ignore[arg-type]
        chapters,
    )
    return service, novels, chapters, scraping_source, result_source


def _novel() -> Novel:
    now = datetime.now(UTC)
    return Novel(
        id="novel-1",
        title="Novel",
        description=None,
        cover_image_url=None,
        language=None,
        author=None,
        tags=[],
        notes=None,
        created_by="owner",
        created_at=now,
        updated_by="owner",
        updated_at=now,
    )


def _scraping(tasks: list[ScrapingTask]) -> Scraping:
    now = datetime.now(UTC)
    return Scraping(
        id="scraping-1",
        crawler_id="novel543",
        source_url="https://example.test/novel",
        metadata=ScrapingMetadata(
            source_novel_id="source-1",
            title="Scraped novel",
            author=None,
            category=None,
            updated_date=None,
            protagonists=[],
            description=None,
            cover_image_url=None,
            fetched_at=now,
        ),
        tasks=tasks,
        progress=ScrapingProgress.from_tasks(tasks),
        idempotency_key="key",
        created_by="different-owner",
        created_at=now,
        updated_at=now,
    )


def _task(
    task_id: str,
    manifest_index: int,
    *,
    result_available: bool = False,
) -> ScrapingTask:
    return ScrapingTask(
        id=task_id,
        source_url=f"https://example.test/{task_id}",
        title=f"Chapter {task_id}",
        chapter_number=manifest_index + 1,
        manifest_index=manifest_index,
        status=(
            ScrapingTaskStatus.COMPLETED
            if result_available
            else ScrapingTaskStatus.CREATED
        ),
        result_available=result_available,
    )


def _result(
    task_id: str,
    content: list[str],
    *,
    updated_at: datetime | None = None,
) -> ScrapingResult:
    now = updated_at or datetime.now(UTC)
    return ScrapingResult(
        id=task_id,
        scraping_id="scraping-1",
        task_id=task_id,
        title=f"Chapter {task_id}",
        chapter_number=1,
        content=content,
        created_at=now,
        updated_at=now,
    )
