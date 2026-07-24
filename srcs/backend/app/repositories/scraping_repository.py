"""Scraping repository contract and in-memory implementation."""

from __future__ import annotations

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
    ScrapingQueueResult,
    ScrapingTaskStatus,
)

MAX_COSMOS_ITEM_BYTES = 1_900_000


class ScrapingRepository(Protocol):
    """Persistence contract for Scrapings."""

    def create_or_merge(self, candidate: Scraping) -> ScrapingCreateResult: ...

    def get(self, id: str, created_by: str | None = None) -> Scraping | None: ...

    def delete(self, id: str, created_by: str) -> None: ...

    def list(
        self,
        created_by: str | None,
        limit: int,
        continuation_token: str | None,
    ) -> ScrapingPage: ...

    def queue_tasks(
        self,
        id: str,
        created_by: str,
        *,
        chapter_from: int,
        chapter_to: int,
        force: bool,
        etag: str | None = None,
    ) -> ScrapingQueueResult: ...

    def stop_queued_tasks(
        self,
        id: str,
        created_by: str,
        *,
        etag: str | None = None,
    ) -> Scraping: ...

    def claim_task(
        self,
        id: str,
        created_by: str,
        task_id: str,
        *,
        etag: str | None = None,
    ) -> Scraping | None: ...

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


class ScrapingNotFoundError(Exception):
    """Raised when a Scraping cannot be found."""


class ScrapingConflictError(Exception):
    """Raised when optimistic concurrency or a state transition conflicts."""


class ScrapingTooLargeError(ValueError):
    """Raised when a Scraping cannot fit in one Cosmos item."""


class ScrapingContinuationTokenError(ValueError):
    """Raised when an in-memory continuation token is invalid."""


class ScrapingChapterRangeError(ValueError):
    """Raised when a chapter-number range matches no tasks."""


class InMemoryScrapingRepository:
    """Thread-safe in-memory Scraping repository used by tests."""

    def __init__(self) -> None:
        self._scrapings: dict[tuple[str, str], Scraping] = {}
        self._lock = Lock()

    def create_or_merge(self, candidate: Scraping) -> ScrapingCreateResult:
        ensure_scraping_size(candidate)
        with self._lock:
            existing = self._find_by_idempotency(
                candidate.created_by,
                candidate.idempotency_key,
            )
            if existing is not None:
                merge_scraping(existing, candidate)
                existing.etag = self._next_etag()
                ensure_scraping_size(existing)
                return ScrapingCreateResult(scraping=deepcopy(existing), created=False)

            stored = deepcopy(candidate)
            stored.etag = self._next_etag()
            self._scrapings[(stored.created_by, stored.id)] = stored
            return ScrapingCreateResult(scraping=deepcopy(stored), created=True)

    def get(self, id: str, created_by: str | None = None) -> Scraping | None:
        with self._lock:
            if created_by is None:
                scraping = next(
                    (
                        item
                        for (_, scraping_id), item in self._scrapings.items()
                        if scraping_id == id
                    ),
                    None,
                )
            else:
                scraping = self._scrapings.get((created_by, id))
            return deepcopy(scraping) if scraping is not None else None

    def delete(self, id: str, created_by: str) -> None:
        with self._lock:
            if self._scrapings.pop((created_by, id), None) is None:
                raise ScrapingNotFoundError

    def list(
        self,
        created_by: str | None,
        limit: int,
        continuation_token: str | None,
    ) -> ScrapingPage:
        try:
            offset = int(continuation_token or "0")
        except ValueError as exc:
            raise ScrapingContinuationTokenError("Invalid continuation token") from exc

        with self._lock:
            items = [
                deepcopy(scraping)
                for (owner, _), scraping in self._scrapings.items()
                if (created_by is None or owner == created_by)
            ]
        items.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        page = items[offset : offset + limit]
        next_offset = offset + len(page)
        next_token = str(next_offset) if next_offset < len(items) else None
        return ScrapingPage(items=page, continuation_token=next_token)

    def queue_tasks(
        self,
        id: str,
        created_by: str,
        *,
        chapter_from: int,
        chapter_to: int,
        force: bool,
        etag: str | None = None,
    ) -> ScrapingQueueResult:
        with self._lock:
            scraping = self._require(id, created_by)
            self._check_etag(scraping, etag)
            matching = [
                task
                for task in scraping.tasks
                if task.chapter_number is not None
                and chapter_from <= task.chapter_number <= chapter_to
            ]
            if not matching:
                raise ScrapingChapterRangeError(
                    "No scraping tasks match the requested chapter range"
                )

            queued = [
                task
                for task in matching
                if force
                or task.status
                not in {ScrapingTaskStatus.QUEUED, ScrapingTaskStatus.RUNNING}
            ]
            if queued:
                for task in queued:
                    task.status = ScrapingTaskStatus.QUEUED
                    task.last_error = None
                touch_scraping(scraping)
                scraping.etag = self._next_etag()
                ensure_scraping_size(scraping)
            return ScrapingQueueResult(
                scraping=deepcopy(scraping),
                tasks=deepcopy(queued),
            )

    def stop_queued_tasks(
        self,
        id: str,
        created_by: str,
        *,
        etag: str | None = None,
    ) -> Scraping:
        with self._lock:
            scraping = self._require(id, created_by)
            self._check_etag(scraping, etag)
            queued = [
                task
                for task in scraping.tasks
                if task.status == ScrapingTaskStatus.QUEUED
            ]
            if queued:
                for task in queued:
                    task.status = ScrapingTaskStatus.CREATED
                touch_scraping(scraping)
                scraping.etag = self._next_etag()
                ensure_scraping_size(scraping)
            return deepcopy(scraping)

    def claim_task(
        self,
        id: str,
        created_by: str,
        task_id: str,
        *,
        etag: str | None = None,
    ) -> Scraping | None:
        with self._lock:
            scraping = self._require(id, created_by)
            self._check_etag(scraping, etag)
            task = next((item for item in scraping.tasks if item.id == task_id), None)
            if task is None:
                raise ScrapingNotFoundError
            if task.status != ScrapingTaskStatus.QUEUED:
                return None

            task.status = ScrapingTaskStatus.RUNNING
            task.attempts += 1
            task.last_error = None
            touch_scraping(scraping)
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
            touch_scraping(scraping)
            scraping.etag = self._next_etag()
            ensure_scraping_size(scraping)
            return deepcopy(scraping)

    def _find_by_idempotency(
        self,
        created_by: str,
        idempotency_key: str,
    ) -> Scraping | None:
        return next(
            (
                scraping
                for scraping in self._scrapings.values()
                if scraping.created_by == created_by
                and scraping.idempotency_key == idempotency_key
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


def merge_scraping(existing: Scraping, candidate: Scraping) -> None:
    existing.crawler_id = candidate.crawler_id
    existing.source_url = candidate.source_url
    existing.metadata = deepcopy(candidate.metadata)

    candidate_tasks = {task.id: task for task in candidate.tasks}
    existing_ids = {task.id for task in existing.tasks}
    for task in existing.tasks:
        refreshed = candidate_tasks.get(task.id)
        if refreshed is None:
            continue
        task.source_url = refreshed.source_url
        task.title = refreshed.title
        task.chapter_number = refreshed.chapter_number

    next_index = max((task.manifest_index for task in existing.tasks), default=-1) + 1
    for candidate_task in candidate.tasks:
        if candidate_task.id in existing_ids:
            continue
        appended = deepcopy(candidate_task)
        appended.manifest_index = next_index
        next_index += 1
        existing.tasks.append(appended)
    touch_scraping(existing)


def touch_scraping(scraping: Scraping) -> None:
    scraping.progress = ScrapingProgress.from_tasks(scraping.tasks)
    scraping.updated_at = datetime.now(UTC)


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
