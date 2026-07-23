"""Scraping result repository contract and in-memory implementation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol

from app.domain.scraping_results import ScrapingResult
from app.repositories.scraping_repository import MAX_COSMOS_ITEM_BYTES, serialized_size


class ScrapingResultRepository(Protocol):
    """Persistence contract for one result per embedded scraping task."""

    def get(self, scraping_id: str, task_id: str) -> ScrapingResult | None: ...

    def upsert(self, result: ScrapingResult) -> ScrapingResult: ...


class ScrapingResultTooLargeError(ValueError):
    """Raised when one task result cannot fit in a Cosmos item."""


class InMemoryScrapingResultRepository:
    """Thread-safe in-memory result repository used by tests."""

    def __init__(self) -> None:
        self._results: dict[tuple[str, str], ScrapingResult] = {}
        self._lock = Lock()

    def get(self, scraping_id: str, task_id: str) -> ScrapingResult | None:
        with self._lock:
            result = self._results.get((scraping_id, task_id))
            return deepcopy(result) if result is not None else None

    def upsert(self, result: ScrapingResult) -> ScrapingResult:
        if result.id != result.task_id:
            raise ValueError("ScrapingResult id must equal taskId")
        if serialized_size(asdict(result)) > MAX_COSMOS_ITEM_BYTES:
            raise ScrapingResultTooLargeError("Scraping result is too large")

        with self._lock:
            stored = deepcopy(result)
            current = self._results.get((stored.scraping_id, stored.task_id))
            if current is not None:
                stored.created_at = current.created_at
            stored.updated_at = datetime.now(UTC)
            stored.etag = datetime.now(UTC).isoformat()
            self._results[(stored.scraping_id, stored.task_id)] = stored
            return deepcopy(stored)
