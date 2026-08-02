"""Novel repository contracts and in-memory implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Protocol

from app.core.exceptions import ConflictException, NotFoundException
from app.domain.novels import Novel, NovelPage


class NovelRepository(Protocol):
    """Persistence contract for novel records."""

    def create(self, novel: Novel) -> Novel: ...

    def get_by_id(self, id: str) -> Novel: ...

    def list(self, limit: int, continuation_token: str | None) -> NovelPage: ...

    def update(self, novel: Novel, etag: str | None) -> Novel: ...

    def delete(self, id: str, etag: str | None, deleted_by: str) -> None: ...


class NovelNotFoundError(NotFoundException):
    """Raised when a novel cannot be found."""

    def __init__(self) -> None:
        super().__init__("Novel not found")


class NovelConflictError(ConflictException):
    """Raised when optimistic concurrency validation fails."""

    def __init__(self) -> None:
        super().__init__("Novel has changed")


class InMemoryNovelRepository:
    """Simple repository used for tests."""

    def __init__(self) -> None:
        self._novels: dict[str, Novel] = {}

    def create(self, novel: Novel) -> Novel:
        stored = deepcopy(novel)
        stored.etag = self._next_etag()
        self._novels[stored.id] = stored
        return deepcopy(stored)

    def get_by_id(self, id: str) -> Novel:
        novel = self._novels.get(id)
        if novel is None or novel.deleted_at is not None:
            raise NovelNotFoundError()
        return deepcopy(novel)

    def list(self, limit: int, continuation_token: str | None) -> NovelPage:
        del continuation_token
        novels = [
            deepcopy(novel)
            for novel in self._novels.values()
            if novel.deleted_at is None
        ]
        novels.sort(key=lambda item: item.created_at)
        return NovelPage(items=novels[:limit], continuation_token=None)

    def update(self, novel: Novel, etag: str | None) -> Novel:
        current = self._novels.get(novel.id)
        if current is None or current.deleted_at is not None:
            raise NovelNotFoundError()
        if current.created_by != novel.created_by:
            raise NovelNotFoundError()
        if etag is not None and current.etag != etag:
            raise NovelConflictError()

        stored = deepcopy(novel)
        stored.etag = self._next_etag()
        self._novels[stored.id] = stored
        return deepcopy(stored)

    def delete(self, id: str, etag: str | None, deleted_by: str) -> None:
        current = self._novels.get(id)
        if current is None or current.deleted_at is not None:
            raise NovelNotFoundError()
        if etag is not None and current.etag != etag:
            raise NovelConflictError()

        now = datetime.now(UTC)
        current.deleted_at = now
        current.deleted_by = deleted_by
        current.updated_at = now
        current.updated_by = deleted_by
        current.etag = self._next_etag()

    @staticmethod
    def _next_etag() -> str:
        return datetime.now(UTC).isoformat()
