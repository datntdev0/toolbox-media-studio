"""Translation result repository contract and in-memory implementation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol

from app.domain.translation_results import TranslationResult
from app.repositories.scraping_repository import MAX_COSMOS_ITEM_BYTES, serialized_size


class TranslationResultRepository(Protocol):
    """Persistence contract for one result per embedded translation task."""

    def get(self, translation_id: str, task_id: str) -> TranslationResult | None: ...

    def upsert(self, result: TranslationResult) -> TranslationResult: ...

    def delete_by_translation(self, translation_id: str) -> None: ...


class TranslationResultTooLargeError(ValueError):
    """Raised when one translated chapter cannot fit in a Cosmos item."""


class InMemoryTranslationResultRepository:
    """Thread-safe in-memory translation result repository."""

    def __init__(self) -> None:
        self._results: dict[tuple[str, str], TranslationResult] = {}
        self._lock = Lock()

    def get(self, translation_id: str, task_id: str) -> TranslationResult | None:
        with self._lock:
            result = self._results.get((translation_id, task_id))
            return deepcopy(result) if result is not None else None

    def upsert(self, result: TranslationResult) -> TranslationResult:
        if result.id != result.task_id:
            raise ValueError("TranslationResult id must equal taskId")
        if serialized_size(asdict(result)) > MAX_COSMOS_ITEM_BYTES:
            raise TranslationResultTooLargeError("Translation result is too large")
        with self._lock:
            stored = deepcopy(result)
            current = self._results.get((stored.translation_id, stored.task_id))
            if current is not None:
                stored.created_at = current.created_at
            stored.updated_at = datetime.now(UTC)
            stored.etag = datetime.now(UTC).isoformat()
            self._results[(stored.translation_id, stored.task_id)] = stored
            return deepcopy(stored)

    def delete_by_translation(self, translation_id: str) -> None:
        with self._lock:
            keys = [key for key in self._results if key[0] == translation_id]
            for key in keys:
                del self._results[key]
