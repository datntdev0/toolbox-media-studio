"""Novel repository contracts and in-memory implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Protocol

from app.domain.novels import Novel, NovelPage, NovelStatus


class NovelRepository(Protocol):
    """Persistence contract for novel records."""

    def create(self, novel: Novel) -> Novel: ...

    def get_by_id(self, id: str, created_by: str) -> Novel | None: ...

    def list(self, created_by: str, limit: int, continuation_token: str | None) -> NovelPage: ...

    def update(self, novel: Novel, etag: str | None) -> Novel: ...

    def delete(self, id: str, created_by: str, etag: str | None, deleted_by: str) -> None: ...


class NovelNotFoundError(Exception):
    """Raised when a novel cannot be found."""


class NovelConflictError(Exception):
    """Raised when optimistic concurrency validation fails."""


class InMemoryNovelRepository:
    """Simple repository used for tests."""

    def __init__(self) -> None:
        self._novels: dict[str, Novel] = {}

    def create(self, novel: Novel) -> Novel:
        stored = deepcopy(novel)
        stored.etag = self._next_etag()
        self._novels[stored.id] = stored
        return deepcopy(stored)

    def get_by_id(self, id: str, created_by: str) -> Novel | None:
        novel = self._novels.get(id)
        if novel is None:
            return None
        if novel.created_by != created_by or novel.status == NovelStatus.DELETED:
            return None
        return deepcopy(novel)

    def list(self, created_by: str, limit: int, continuation_token: str | None) -> NovelPage:
        del continuation_token
        novels = [
            deepcopy(novel)
            for novel in self._novels.values()
            if novel.created_by == created_by and novel.status != NovelStatus.DELETED
        ]
        novels.sort(key=lambda item: item.created_at)
        return NovelPage(items=novels[:limit], continuation_token=None)

    def update(self, novel: Novel, etag: str | None) -> Novel:
        current = self._novels.get(novel.id)
        if current is None or current.status == NovelStatus.DELETED:
            raise NovelNotFoundError
        if current.created_by != novel.created_by:
            raise NovelNotFoundError
        if etag is not None and current.etag != etag:
            raise NovelConflictError

        stored = deepcopy(novel)
        stored.etag = self._next_etag()
        self._novels[stored.id] = stored
        return deepcopy(stored)

    def delete(self, id: str, created_by: str, etag: str | None, deleted_by: str) -> None:
        current = self._novels.get(id)
        if current is None or current.status == NovelStatus.DELETED:
            raise NovelNotFoundError
        if current.created_by != created_by:
            raise NovelNotFoundError
        if etag is not None and current.etag != etag:
            raise NovelConflictError

        now = datetime.now(UTC)
        current.status = NovelStatus.DELETED
        current.deleted_at = now
        current.deleted_by = deleted_by
        current.updated_at = now
        current.updated_by = deleted_by
        current.etag = self._next_etag()

    @staticmethod
    def _next_etag() -> str:
        return datetime.now(UTC).isoformat()
