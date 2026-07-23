"""Scraping repository contract and in-memory implementation."""

from __future__ import annotations

import builtins
import json
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from threading import Lock
from typing import Protocol

from app.domain.scrapings import (
    Scraping,
    ScrapingCreateResult,
    ScrapingPage,
    ScrapingProgress,
    ScrapingStatus,
    ScrapingTaskStatus,
)

MAX_COSMOS_ITEM_BYTES = 1_900_000


class ScrapingRepository(Protocol):
    """Persistence contract for Scrapings."""

    def create_or_get_active(self, candidate: Scraping) -> ScrapingCreateResult: ...

    def get(self, id: str, created_by: str) -> Scraping | None: ...

    def list(
        self,
        created_by: str,
        limit: int,
        continuation_token: str | None,
        status: ScrapingStatus | None,
    ) -> ScrapingPage: ...

    def set_status(
        self,
        id: str,
        created_by: str,
        status: ScrapingStatus,
        *,
        attempt: int | None = None,
        error: str | None = None,
        etag: str | None = None,
    ) -> Scraping: ...

    def update_task(
        self,
        id: str,
        created_by: str,
        task_id: str,
        status: ScrapingTaskStatus,
        *,
        attempts: int,
        error: str | None,
        result_available: bool,
        completed_at: datetime | None,
        etag: str | None = None,
    ) -> Scraping: ...

    def reconcile(self, id: str, created_by: str, etag: str | None = None) -> Scraping: ...

    def list_stale_active(
        self,
        updated_before: datetime,
        limit: int,
    ) -> builtins.list[Scraping]: ...


class ScrapingNotFoundError(Exception):
    """Raised when a Scraping cannot be found."""


class ScrapingConflictError(Exception):
    """Raised when optimistic concurrency or a state transition conflicts."""


class ScrapingTooLargeError(ValueError):
    """Raised when a Scraping cannot fit in one Cosmos item."""


class ScrapingContinuationTokenError(ValueError):
    """Raised when an in-memory continuation token is invalid."""


class InMemoryScrapingRepository:
    """Thread-safe in-memory Scraping repository used by tests."""

    def __init__(self) -> None:
        self._scrapings: dict[tuple[str, str], Scraping] = {}
        self._lock = Lock()

    def create_or_get_active(self, candidate: Scraping) -> ScrapingCreateResult:
        ensure_scraping_size(candidate)
        with self._lock:
            active = self._find_active(candidate.created_by, candidate.idempotency_key)
            if active is not None:
                return ScrapingCreateResult(scraping=deepcopy(active), created=False)

            stored = deepcopy(candidate)
            stored.active_key = stored.idempotency_key
            stored.etag = self._next_etag()
            self._scrapings[(stored.created_by, stored.id)] = stored
            return ScrapingCreateResult(scraping=deepcopy(stored), created=True)

    def get(self, id: str, created_by: str) -> Scraping | None:
        with self._lock:
            scraping = self._scrapings.get((created_by, id))
            return deepcopy(scraping) if scraping is not None else None

    def list(
        self,
        created_by: str,
        limit: int,
        continuation_token: str | None,
        status: ScrapingStatus | None,
    ) -> ScrapingPage:
        try:
            offset = int(continuation_token or "0")
        except ValueError as exc:
            raise ScrapingContinuationTokenError("Invalid continuation token") from exc

        with self._lock:
            items = [
                deepcopy(scraping)
                for (owner, _), scraping in self._scrapings.items()
                if owner == created_by and (status is None or scraping.status == status)
            ]
        items.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        page = items[offset : offset + limit]
        next_offset = offset + len(page)
        next_token = str(next_offset) if next_offset < len(items) else None
        return ScrapingPage(items=page, continuation_token=next_token)

    def set_status(
        self,
        id: str,
        created_by: str,
        status: ScrapingStatus,
        *,
        attempt: int | None = None,
        error: str | None = None,
        etag: str | None = None,
    ) -> Scraping:
        with self._lock:
            scraping = self._require(id, created_by)
            self._check_etag(scraping, etag)
            if scraping.status.is_terminal and status != scraping.status:
                raise ScrapingConflictError("Terminal Scrapings cannot change status")

            now = datetime.now(UTC)
            scraping.status = status
            if attempt is not None:
                scraping.attempts = max(scraping.attempts, attempt)
            scraping.last_error = error
            scraping.updated_at = now
            if status.is_terminal:
                scraping.active_key = f"terminal:{scraping.id}"
                scraping.completed_at = now
            scraping.etag = self._next_etag()
            ensure_scraping_size(scraping)
            return deepcopy(scraping)

    def update_task(
        self,
        id: str,
        created_by: str,
        task_id: str,
        status: ScrapingTaskStatus,
        *,
        attempts: int,
        error: str | None,
        result_available: bool,
        completed_at: datetime | None,
        etag: str | None = None,
    ) -> Scraping:
        with self._lock:
            scraping = self._require(id, created_by)
            self._check_etag(scraping, etag)
            task = next((item for item in scraping.tasks if item.id == task_id), None)
            if task is None:
                raise ScrapingNotFoundError

            task.status = status
            task.attempts = max(task.attempts, attempts)
            task.last_error = error
            task.result_available = result_available
            task.completed_at = completed_at
            scraping.progress = ScrapingProgress.from_tasks(scraping.tasks)
            scraping.updated_at = datetime.now(UTC)
            scraping.etag = self._next_etag()
            ensure_scraping_size(scraping)
            return deepcopy(scraping)

    def reconcile(self, id: str, created_by: str, etag: str | None = None) -> Scraping:
        with self._lock:
            scraping = self._require(id, created_by)
            self._check_etag(scraping, etag)
            scraping.progress = ScrapingProgress.from_tasks(scraping.tasks)
            now = datetime.now(UTC)
            scraping.status = reconciled_scraping_status(scraping.progress)

            if scraping.status.is_terminal:
                scraping.active_key = f"terminal:{scraping.id}"
                scraping.completed_at = now
            scraping.updated_at = now
            scraping.etag = self._next_etag()
            ensure_scraping_size(scraping)
            return deepcopy(scraping)

    def list_stale_active(
        self,
        updated_before: datetime,
        limit: int,
    ) -> builtins.list[Scraping]:
        with self._lock:
            items = [
                deepcopy(scraping)
                for scraping in self._scrapings.values()
                if scraping.status.is_active and scraping.updated_at < updated_before
            ]
        items.sort(key=lambda item: item.updated_at)
        return items[:limit]

    def _find_active(self, created_by: str, idempotency_key: str) -> Scraping | None:
        return next(
            (
                scraping
                for scraping in self._scrapings.values()
                if scraping.created_by == created_by
                and scraping.idempotency_key == idempotency_key
                and scraping.status.is_active
            ),
            None,
        )

    def _require(self, id: str, created_by: str) -> Scraping:
        scraping = self._scrapings.get((created_by, id))
        if scraping is None:
            raise ScrapingNotFoundError
        return scraping

    @staticmethod
    def _check_etag(scraping: Scraping, etag: str | None) -> None:
        if etag is not None and scraping.etag != etag:
            raise ScrapingConflictError("Scraping has changed")

    @staticmethod
    def _next_etag() -> str:
        return datetime.now(UTC).isoformat()


def ensure_scraping_size(scraping: Scraping) -> None:
    if serialized_size(asdict(scraping)) > MAX_COSMOS_ITEM_BYTES:
        raise ScrapingTooLargeError("Scraping chapter manifest is too large")


def reconciled_scraping_status(progress: ScrapingProgress) -> ScrapingStatus:
    """Derive the aggregate status without abandoning retryable tasks."""

    terminal_count = progress.completed + progress.failed
    if terminal_count == progress.total:
        return ScrapingStatus.FAILED if progress.failed else ScrapingStatus.COMPLETED
    if progress.retrying:
        return ScrapingStatus.RETRYING
    return ScrapingStatus.PROCESSING


def serialized_size(value: object) -> int:
    return len(
        json.dumps(
            value,
            default=_json_default,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)
