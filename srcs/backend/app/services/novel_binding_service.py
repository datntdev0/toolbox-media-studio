"""Synchronous novel binding, synchronization, and chapter-content workflows."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.domain.novels import Novel, NovelBinding, NovelChapter, NovelSyncResult
from app.repositories.novel_chapter_repository import (
    NovelChapterConflictError,
    NovelChapterRepository,
)
from app.repositories.novel_repository import (
    NovelConflictError,
    NovelNotFoundError,
    NovelRepository,
)
from app.repositories.scraping_repository import ScrapingRepository
from app.repositories.scraping_result_repository import ScrapingResultRepository


class NovelBindingNotFoundError(Exception):
    """Raised when a novel, scraping, or chapter cannot be found."""


class NovelBindingConflictError(Exception):
    """Raised when the requested workflow conflicts with current state."""


class NovelBindingConcurrencyError(Exception):
    """Raised when a write loses an optimistic-concurrency race."""


class NovelBindingService:
    """Coordinates cloned chapter metadata and private content."""

    def __init__(
        self,
        novel_repository: NovelRepository,
        scraping_repository: ScrapingRepository,
        scraping_result_repository: ScrapingResultRepository,
        chapter_repository: NovelChapterRepository,
    ) -> None:
        self._novels = novel_repository
        self._scrapings = scraping_repository
        self._results = scraping_result_repository
        self._chapters = chapter_repository

    def get_detail(self, novel_id: str) -> tuple[Novel, list[NovelChapter]]:
        novel = self._novels.get_by_id(novel_id)
        if novel is None:
            raise NovelBindingNotFoundError("Novel not found")
        return novel, self._chapters.list(novel_id).items

    def bind(
        self,
        novel_id: str,
        scraping_id: str,
        *,
        updated_by: str,
    ) -> NovelSyncResult:
        novel = self._novels.get_by_id(novel_id)
        if novel is None:
            raise NovelBindingNotFoundError("Novel not found")
        existing_chapters = self._chapters.list(novel_id).items
        if novel.binding is not None or novel.chapter_count != 0 or existing_chapters:
            raise NovelBindingConflictError(
                "Novel must be unbound and have no chapters"
            )
        scraping = self._scrapings.get(scraping_id)
        if scraping is None:
            raise NovelBindingNotFoundError("Scraping not found")

        now = datetime.now(UTC)
        chapters: list[NovelChapter] = []
        try:
            for task in sorted(
                scraping.tasks,
                key=lambda item: (item.manifest_index, item.id),
            ):
                result = (
                    self._results.get(scraping.id, task.id)
                    if task.result_available
                    else None
                )
                chapter = NovelChapter(
                    id=task.id,
                    novel_id=novel.id,
                    scraping_task_id=task.id,
                    title=task.title,
                    chapter_number=task.chapter_number,
                    manifest_index=task.manifest_index,
                    source_url=task.source_url,
                    content=list(result.content) if result is not None else [],
                    content_available=result is not None,
                    manually_edited=False,
                    source_updated=False,
                    source_removed=False,
                    source_result_updated_at=result.updated_at if result else None,
                    created_at=now,
                    updated_at=now,
                    updated_by=updated_by,
                )
                chapters.append(self._chapters.save(chapter))

            novel.binding = NovelBinding(
                scraping_id=scraping.id,
                bound_at=now,
                last_synced_at=now,
            )
            novel.chapter_count = len(chapters)
            novel.updated_by = updated_by
            novel.updated_at = now
            novel = self._novels.update(novel, novel.etag)
        except (NovelConflictError, NovelNotFoundError) as exc:
            self._chapters.delete_by_novel(novel_id)
            if isinstance(exc, NovelConflictError):
                raise NovelBindingConcurrencyError("Novel has changed") from exc
            raise NovelBindingNotFoundError("Novel not found") from exc
        except Exception:
            self._chapters.delete_by_novel(novel_id)
            raise

        return NovelSyncResult(
            novel=novel,
            chapters=chapters,
            added=len(chapters),
            refreshed=0,
            preserved=0,
            removed=0,
        )

    def sync(self, novel_id: str, *, updated_by: str) -> NovelSyncResult:
        novel = self._novels.get_by_id(novel_id)
        if novel is None:
            raise NovelBindingNotFoundError("Novel not found")
        if novel.binding is None:
            raise NovelBindingConflictError("Novel is not bound")
        scraping = self._scrapings.get(novel.binding.scraping_id)
        if scraping is None:
            raise NovelBindingNotFoundError("Bound scraping not found")

        now = datetime.now(UTC)
        existing = {
            chapter.scraping_task_id: chapter
            for chapter in self._chapters.list(novel_id).items
        }
        updated_chapters: list[NovelChapter] = []
        added = refreshed = preserved = removed = 0

        for task in sorted(
            scraping.tasks,
            key=lambda item: (item.manifest_index, item.id),
        ):
            chapter = existing.pop(task.id, None)
            result = (
                self._results.get(scraping.id, task.id)
                if task.result_available
                else None
            )
            if chapter is None:
                chapter = NovelChapter(
                    id=task.id,
                    novel_id=novel.id,
                    scraping_task_id=task.id,
                    title=task.title,
                    chapter_number=task.chapter_number,
                    manifest_index=task.manifest_index,
                    source_url=task.source_url,
                    content=list(result.content) if result is not None else [],
                    content_available=result is not None,
                    manually_edited=False,
                    source_updated=False,
                    source_removed=False,
                    source_result_updated_at=result.updated_at if result else None,
                    created_at=now,
                    updated_at=now,
                    updated_by=updated_by,
                )
                added += 1
            else:
                source_is_newer = (
                    result is not None
                    and (
                        chapter.source_result_updated_at is None
                        or result.updated_at > chapter.source_result_updated_at
                    )
                )
                metadata_changed = (
                    chapter.title != task.title
                    or chapter.chapter_number != task.chapter_number
                    or chapter.manifest_index != task.manifest_index
                    or chapter.source_url != task.source_url
                    or chapter.source_removed
                )
                chapter.title = task.title
                chapter.chapter_number = task.chapter_number
                chapter.manifest_index = task.manifest_index
                chapter.source_url = task.source_url
                chapter.source_removed = False
                if chapter.manually_edited:
                    chapter.source_updated = source_is_newer
                    if source_is_newer:
                        preserved += 1
                elif result is not None and (
                    source_is_newer or not chapter.content_available
                ):
                    chapter.content = list(result.content)
                    chapter.content_available = True
                    chapter.source_result_updated_at = result.updated_at
                    chapter.source_updated = False
                    refreshed += 1
                elif metadata_changed:
                    refreshed += 1
                chapter.updated_at = now
                chapter.updated_by = updated_by

            try:
                updated_chapters.append(
                    self._chapters.save(chapter, etag=chapter.etag)
                )
            except NovelChapterConflictError as exc:
                raise NovelBindingConcurrencyError(
                    "Novel chapter has changed"
                ) from exc

        for chapter in existing.values():
            if not chapter.source_removed:
                chapter.source_removed = True
                chapter.updated_at = now
                removed += 1
            chapter.updated_by = updated_by
            try:
                updated_chapters.append(
                    self._chapters.save(chapter, etag=chapter.etag)
                )
            except NovelChapterConflictError as exc:
                raise NovelBindingConcurrencyError(
                    "Novel chapter has changed"
                ) from exc

        updated_chapters.sort(key=lambda item: (item.manifest_index, item.id))
        novel.binding = NovelBinding(
            scraping_id=scraping.id,
            bound_at=novel.binding.bound_at,
            last_synced_at=now,
        )
        novel.chapter_count = len(updated_chapters)
        novel.updated_by = updated_by
        novel.updated_at = now
        try:
            novel = self._novels.update(novel, novel.etag)
        except NovelConflictError as exc:
            raise NovelBindingConcurrencyError("Novel has changed") from exc
        except NovelNotFoundError as exc:
            raise NovelBindingNotFoundError("Novel not found") from exc

        return NovelSyncResult(
            novel=novel,
            chapters=updated_chapters,
            added=added,
            refreshed=refreshed,
            preserved=preserved,
            removed=removed,
        )

    def get_chapter_content(
        self,
        novel_id: str,
        chapter_id: str,
    ) -> tuple[NovelChapter, list[str]]:
        if self._novels.get_by_id(novel_id) is None:
            raise NovelBindingNotFoundError("Novel not found")
        chapter = self._chapters.get(novel_id, chapter_id)
        if chapter is None:
            raise NovelBindingNotFoundError("Novel chapter not found")
        return chapter, list(chapter.content) if chapter.content_available else []

    def update_chapter_content(
        self,
        novel_id: str,
        chapter_id: str,
        content: str,
        *,
        etag: str,
        updated_by: str | None = None,
    ) -> tuple[NovelChapter, list[str]]:
        if self._novels.get_by_id(novel_id) is None:
            raise NovelBindingNotFoundError("Novel not found")
        chapter = self._chapters.get(novel_id, chapter_id)
        if chapter is None:
            raise NovelBindingNotFoundError("Novel chapter not found")
        normalized = content.replace("\r\n", "\n").strip()
        paragraphs = (
            [
                paragraph.strip()
                for paragraph in re.split(r"\n[ \t]*\n+", normalized)
                if paragraph.strip()
            ]
            if normalized
            else []
        )
        chapter.content = paragraphs
        chapter.content_available = True
        chapter.manually_edited = True
        chapter.source_updated = False
        chapter.updated_at = datetime.now(UTC)
        chapter.updated_by = updated_by
        try:
            chapter = self._chapters.save(chapter, etag=etag)
        except NovelChapterConflictError as exc:
            raise NovelBindingConcurrencyError(
                "Novel chapter has changed"
            ) from exc
        return chapter, paragraphs
