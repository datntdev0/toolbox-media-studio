"""Novel chapter repository contract and in-memory implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol

from app.domain.novels import NovelChapter, NovelChapterPage


class NovelChapterRepository(Protocol):
    """Persistence contract for chapters partitioned by novel."""

    def get(self, novel_id: str, chapter_id: str) -> NovelChapter | None: ...

    def list(self, novel_id: str) -> NovelChapterPage: ...

    def save(
        self,
        chapter: NovelChapter,
        *,
        etag: str | None = None,
    ) -> NovelChapter: ...

    def delete_by_novel(self, novel_id: str) -> None: ...


class NovelChapterNotFoundError(Exception):
    """Raised when a chapter cannot be found."""


class NovelChapterConflictError(Exception):
    """Raised when optimistic concurrency validation fails."""


class InMemoryNovelChapterRepository:
    """Thread-safe in-memory chapter repository including content."""

    def __init__(self) -> None:
        self._chapters: dict[tuple[str, str], NovelChapter] = {}
        self._lock = Lock()

    def get(self, novel_id: str, chapter_id: str) -> NovelChapter | None:
        with self._lock:
            chapter = self._chapters.get((novel_id, chapter_id))
            return deepcopy(chapter) if chapter is not None else None

    def list(self, novel_id: str) -> NovelChapterPage:
        with self._lock:
            chapters = [
                deepcopy(chapter)
                for (partition, _), chapter in self._chapters.items()
                if partition == novel_id
            ]
        chapters.sort(key=lambda item: (item.manifest_index, item.id))
        return NovelChapterPage(items=chapters)

    def save(
        self,
        chapter: NovelChapter,
        *,
        etag: str | None = None,
    ) -> NovelChapter:
        with self._lock:
            key = (chapter.novel_id, chapter.id)
            current = self._chapters.get(key)
            if etag is not None and (current is None or current.etag != etag):
                raise NovelChapterConflictError("Novel chapter has changed")
            stored = deepcopy(chapter)
            if current is not None:
                stored.created_at = current.created_at
            stored.etag = datetime.now(UTC).isoformat()
            self._chapters[key] = stored
            return deepcopy(stored)

    def delete_by_novel(self, novel_id: str) -> None:
        with self._lock:
            keys = [key for key in self._chapters if key[0] == novel_id]
            for key in keys:
                del self._chapters[key]
