"""Translation repository contract and in-memory implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Protocol

from app.domain.translations import (
    Translation,
    TranslationPage,
    TranslationProgress,
    TranslationQueueResult,
    TranslationStatus,
    TranslationTask,
    TranslationTaskStatus,
)


class TranslationRepository(Protocol):
    """Persistence contract for translation projects."""

    def create(self, translation: Translation) -> Translation: ...

    def get_by_id(self, id: str) -> Translation | None: ...

    def list(self, limit: int, continuation_token: str | None) -> TranslationPage: ...

    def update(self, translation: Translation, etag: str | None) -> Translation: ...

    def delete(self, id: str, etag: str | None, deleted_by: str) -> None: ...

    def queue_tasks(
        self,
        id: str,
        *,
        chapter_index_from: int,
        chapter_index_to: int,
        force: bool,
        etag: str | None,
    ) -> TranslationQueueResult: ...

    def stop_queued_tasks(self, id: str, *, etag: str | None) -> Translation: ...

    def claim_task(
        self,
        id: str,
        task_id: str,
        *,
        etag: str | None,
    ) -> Translation | None: ...

    def update_task(
        self,
        id: str,
        task_id: str,
        status: TranslationTaskStatus,
        *,
        attempts: int,
        error: str | None,
        result_available: bool,
        completed_at: datetime | None,
        source_chapter_updated_at: datetime | None,
        clear_source_updated: bool,
        etag: str | None,
    ) -> Translation: ...


class TranslationNotFoundError(Exception):
    """Raised when a translation cannot be found."""


class TranslationConflictError(Exception):
    """Raised when optimistic concurrency validation fails."""


class TranslationContinuationTokenError(ValueError):
    """Raised when an in-memory continuation token is invalid."""


class TranslationChapterRangeError(ValueError):
    """Raised when a requested range matches no current tasks."""


class InMemoryTranslationRepository:
    """Simple translation repository used by route and service tests."""

    def __init__(self) -> None:
        self._translations: dict[str, Translation] = {}

    def create(self, translation: Translation) -> Translation:
        stored = deepcopy(translation)
        stored.etag = self._next_etag()
        self._translations[stored.id] = stored
        return deepcopy(stored)

    def get_by_id(self, id: str) -> Translation | None:
        translation = self._translations.get(id)
        if translation is None or translation.status == TranslationStatus.DELETED:
            return None
        return deepcopy(translation)

    def list(self, limit: int, continuation_token: str | None) -> TranslationPage:
        try:
            offset = int(continuation_token or "0")
        except ValueError as exc:
            raise TranslationContinuationTokenError("Invalid continuation token") from exc
        if offset < 0:
            raise TranslationContinuationTokenError("Invalid continuation token")

        translations = [
            deepcopy(translation)
            for translation in self._translations.values()
            if translation.status != TranslationStatus.DELETED
        ]
        translations.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        page = translations[offset : offset + limit]
        next_offset = offset + len(page)
        next_token = str(next_offset) if next_offset < len(translations) else None
        return TranslationPage(items=page, continuation_token=next_token)

    def update(self, translation: Translation, etag: str | None) -> Translation:
        current = self._translations.get(translation.id)
        if current is None or current.status == TranslationStatus.DELETED:
            raise TranslationNotFoundError
        if etag is not None and current.etag != etag:
            raise TranslationConflictError("Translation has changed")

        stored = deepcopy(translation)
        stored.etag = self._next_etag()
        self._translations[stored.id] = stored
        return deepcopy(stored)

    def delete(self, id: str, etag: str | None, deleted_by: str) -> None:
        translation = self._translations.get(id)
        if translation is None or translation.status == TranslationStatus.DELETED:
            raise TranslationNotFoundError
        if etag is not None and translation.etag != etag:
            raise TranslationConflictError("Translation has changed")

        now = datetime.now(UTC)
        translation.status = TranslationStatus.DELETED
        translation.deleted_at = now
        translation.deleted_by = deleted_by
        translation.updated_at = now
        translation.updated_by = deleted_by
        translation.etag = self._next_etag()

    def queue_tasks(
        self,
        id: str,
        *,
        chapter_index_from: int,
        chapter_index_to: int,
        force: bool,
        etag: str | None,
    ) -> TranslationQueueResult:
        translation = self._require(id)
        self._check_etag(translation, etag)
        matching = [
            task
            for task in translation.tasks
            if not task.source_removed
            and chapter_index_from <= task.manifest_index + 1 <= chapter_index_to
        ]
        if not matching:
            raise TranslationChapterRangeError(
                "No translation tasks match the requested chapter index range"
            )
        queued = [
            task
            for task in matching
            if force
            or task.status
            not in {TranslationTaskStatus.QUEUED, TranslationTaskStatus.RUNNING}
        ]
        for task in queued:
            task.status = TranslationTaskStatus.QUEUED
            task.last_error = None
        if queued:
            translation.status = TranslationStatus.RUNNING
            self._touch(translation)
        return TranslationQueueResult(
            translation=deepcopy(translation),
            tasks=deepcopy(queued),
        )

    def stop_queued_tasks(self, id: str, *, etag: str | None) -> Translation:
        translation = self._require(id)
        self._check_etag(translation, etag)
        for task in translation.tasks:
            if task.status == TranslationTaskStatus.QUEUED:
                task.status = TranslationTaskStatus.CREATED
        translation.status = TranslationStatus.STOPPED
        self._touch(translation, reconcile=False)
        return deepcopy(translation)

    def claim_task(
        self,
        id: str,
        task_id: str,
        *,
        etag: str | None,
    ) -> Translation | None:
        translation = self._require(id)
        self._check_etag(translation, etag)
        task = self._require_task(translation, task_id)
        if (
            translation.status == TranslationStatus.STOPPED
            or task.source_removed
            or task.status != TranslationTaskStatus.QUEUED
        ):
            return None
        task.status = TranslationTaskStatus.RUNNING
        task.attempts += 1
        task.last_error = None
        self._touch(translation)
        return deepcopy(translation)

    def update_task(
        self,
        id: str,
        task_id: str,
        status: TranslationTaskStatus,
        *,
        attempts: int,
        error: str | None,
        result_available: bool,
        completed_at: datetime | None,
        source_chapter_updated_at: datetime | None,
        clear_source_updated: bool,
        etag: str | None,
    ) -> Translation:
        translation = self._require(id)
        self._check_etag(translation, etag)
        task = self._require_task(translation, task_id)
        task.status = status
        task.attempts = max(task.attempts, attempts)
        task.last_error = error
        task.result_available = result_available
        task.completed_at = completed_at
        if source_chapter_updated_at is not None:
            task.source_chapter_updated_at = source_chapter_updated_at
        if clear_source_updated:
            task.source_updated = False
        self._touch(translation)
        return deepcopy(translation)

    def _require(self, id: str) -> Translation:
        translation = self._translations.get(id)
        if translation is None or translation.status == TranslationStatus.DELETED:
            raise TranslationNotFoundError
        return translation

    @staticmethod
    def _require_task(
        translation: Translation,
        task_id: str,
    ) -> TranslationTask:
        task = next((item for item in translation.tasks if item.id == task_id), None)
        if task is None:
            raise TranslationNotFoundError
        return task

    @staticmethod
    def _check_etag(translation: Translation, etag: str | None) -> None:
        if etag is not None and translation.etag != etag:
            raise TranslationConflictError("Translation has changed")

    def _touch(self, translation: Translation, *, reconcile: bool = True) -> None:
        translation.progress = TranslationProgress.from_tasks(translation.tasks)
        translation.updated_at = datetime.now(UTC)
        if reconcile:
            translation.status = reconcile_translation_status(translation)
        translation.etag = self._next_etag()

    @staticmethod
    def _next_etag() -> str:
        return datetime.now(UTC).isoformat()


def reconcile_translation_status(translation: Translation) -> TranslationStatus:
    """Derive aggregate status while preserving explicit stop requests."""

    if translation.status == TranslationStatus.STOPPED:
        return TranslationStatus.STOPPED
    progress = translation.progress
    if progress.queued or progress.running:
        return TranslationStatus.RUNNING
    if progress.total and progress.completed == progress.total:
        return TranslationStatus.COMPLETED
    if progress.failed:
        return TranslationStatus.FAILED
    return (
        TranslationStatus.READY
        if translation.configuration is not None
        else TranslationStatus.NEEDS_SETUP
    )
