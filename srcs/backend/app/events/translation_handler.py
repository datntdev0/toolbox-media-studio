"""Queue handler and listener for task-scoped translation events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from logging import Logger
from typing import Any

from app.core.events.message_handler import MessageHandler, QueueMessage
from app.core.events.polling_queue_subscriber import PollingQueueSubscriber
from app.core.realtime import RealtimeHub
from app.domain.translation_results import TranslationResult
from app.domain.translations import Translation, TranslationTask, TranslationTaskStatus
from app.providers.translation_service_provider import TranslationServiceProviderFactory
from app.repositories.novel_chapter_repository import NovelChapterRepository
from app.repositories.translation_repository import (
    TranslationConflictError,
    TranslationNotFoundError,
    TranslationRepository,
)
from app.repositories.translation_result_repository import TranslationResultRepository

TRANSLATION_QUEUE_NAME = "translations"
TRANSLATION_EVENT_TYPE = "translation.task.requested"
TRANSLATION_EVENT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class TranslationEvent:
    """Validated task-scoped translation queue event."""

    translation_id: str
    created_by: str
    task_id: str
    refetch: bool
    enqueued_at: str

    @classmethod
    def from_mapping(cls, content: Mapping[str, Any]) -> TranslationEvent:
        if content.get("schemaVersion") != TRANSLATION_EVENT_SCHEMA_VERSION:
            raise ValueError("Unsupported translation event schema")
        if content.get("type") != TRANSLATION_EVENT_TYPE:
            raise ValueError("Unsupported translation event type")
        refetch = content.get("refetch", False)
        if not isinstance(refetch, bool):
            raise ValueError("Invalid translation event refetch flag")
        return cls(
            translation_id=_required_string(content, "translationId"),
            created_by=_required_string(content, "createdBy"),
            task_id=_required_string(content, "taskId"),
            refetch=refetch,
            enqueued_at=_required_string(content, "enqueuedAt"),
        )


class TranslationHandler(MessageHandler):
    """Translate one queued chapter and persist its isolated result."""

    def __init__(
        self,
        logger: Logger,
        translation_repository: TranslationRepository,
        translation_result_repository: TranslationResultRepository,
        novel_chapter_repository: NovelChapterRepository,
        realtime_hub: RealtimeHub,
        translation_service_provider_factory: TranslationServiceProviderFactory,
    ) -> None:
        self._logger = logger
        self._translations = translation_repository
        self._results = translation_result_repository
        self._chapters = novel_chapter_repository
        self._realtime = realtime_hub
        self._translation_service_provider_factory = translation_service_provider_factory

    def handle(self, message: QueueMessage) -> None:
        if message.content is None:
            raise ValueError("Translation queue message has no content")
        event = TranslationEvent.from_mapping(message.content)
        translation = self._translations.get_by_id(event.translation_id)
        if translation is None or translation.created_by != event.created_by:
            return
        task = _find_task(translation, event.task_id)
        if (
            task is None
            or task.source_removed
            or task.status != TranslationTaskStatus.QUEUED
        ):
            return

        claimed = self._claim_task_with_retry(translation, task.id)
        if claimed is None:
            return
        claimed_task = _require_task(claimed, task.id)
        self._publish_update(claimed, task.id)
        existing = self._results.get(claimed.id, task.id)

        try:
            if existing is not None and not event.refetch:
                completed = self._update_task_with_retry(
                    claimed,
                    task.id,
                    TranslationTaskStatus.COMPLETED,
                    attempts=claimed_task.attempts,
                    error=None,
                    result_available=True,
                    completed_at=datetime.now(UTC),
                    source_chapter_updated_at=None,
                    clear_source_updated=False,
                )
            else:
                chapter = self._chapters.get(claimed.novel_id, task.id)
                if chapter is None or not chapter.content_available or chapter.source_removed:
                    raise ValueError("Source novel chapter content is unavailable")
                configuration = claimed.configuration
                if configuration is None:
                    raise ValueError("Translation configuration is unavailable")
                provider = self._translation_service_provider_factory.get(
                    configuration.provider_id
                )
                translated = provider.translate(
                    model=configuration.model_id,
                    language=claimed.target_language,
                    instruction=configuration.global_prompt,
                    chapter_title=chapter.title,
                    chapter_content=chapter.content,
                )
                now = datetime.now(UTC)
                self._results.upsert(
                    TranslationResult(
                        id=task.id,
                        translation_id=claimed.id,
                        task_id=task.id,
                        title=translated.title,
                        chapter_number=chapter.chapter_number,
                        content=translated.content,
                        created_at=now,
                        updated_at=now,
                    )
                )
                completed = self._update_task_with_retry(
                    claimed,
                    task.id,
                    TranslationTaskStatus.COMPLETED,
                    attempts=claimed_task.attempts,
                    error=None,
                    result_available=True,
                    completed_at=now,
                    source_chapter_updated_at=chapter.updated_at,
                    clear_source_updated=True,
                )
            self._publish_update(completed, task.id)
        except Exception as exc:
            latest = self._translations.get_by_id(claimed.id) or claimed
            try:
                failed = self._update_task_with_retry(
                    latest,
                    task.id,
                    TranslationTaskStatus.FAILED,
                    attempts=claimed_task.attempts,
                    error=str(exc),
                    result_available=existing is not None,
                    completed_at=None,
                    source_chapter_updated_at=None,
                    clear_source_updated=False,
                )
                self._publish_update(failed, task.id)
            except Exception:
                self._logger.exception("Translation task failure state could not be saved")
            raise

    def _claim_task_with_retry(
        self,
        translation: Translation,
        task_id: str,
    ) -> Translation | None:
        for _ in range(3):
            try:
                return self._translations.claim_task(
                    translation.id,
                    task_id,
                    etag=translation.etag,
                )
            except TranslationConflictError:
                latest = self._translations.get_by_id(translation.id)
                if latest is None:
                    return None
                task = _find_task(latest, task_id)
                if (
                    task is None
                    or task.source_removed
                    or task.status != TranslationTaskStatus.QUEUED
                ):
                    return None
                translation = latest
            except TranslationNotFoundError:
                return None
        raise TranslationConflictError("Translation task claim conflicted repeatedly")

    def _update_task_with_retry(
        self,
        translation: Translation,
        task_id: str,
        status: TranslationTaskStatus,
        *,
        attempts: int,
        error: str | None,
        result_available: bool,
        completed_at: datetime | None,
        source_chapter_updated_at: datetime | None,
        clear_source_updated: bool,
    ) -> Translation:
        for _ in range(3):
            try:
                return self._translations.update_task(
                    translation.id,
                    task_id,
                    status,
                    attempts=attempts,
                    error=error,
                    result_available=result_available,
                    completed_at=completed_at,
                    source_chapter_updated_at=source_chapter_updated_at,
                    clear_source_updated=clear_source_updated,
                    etag=translation.etag,
                )
            except TranslationConflictError:
                latest = self._translations.get_by_id(translation.id)
                if latest is None:
                    raise TranslationNotFoundError from None
                translation = latest
        raise TranslationConflictError("Translation task update conflicted repeatedly")

    def _publish_update(self, translation: Translation, task_id: str | None = None) -> None:
        self._realtime.publish(
            "translation.updated",
            build_translation_updated_payload(translation, task_id=task_id),
        )


class TranslationQueueListener(PollingQueueSubscriber):
    """Queue listener configured with the translation provider."""

    def __init__(
        self,
        logger: Logger,
        translation_repository: TranslationRepository,
        translation_result_repository: TranslationResultRepository,
        novel_chapter_repository: NovelChapterRepository,
        realtime_hub: RealtimeHub,
        translation_service_provider_factory: TranslationServiceProviderFactory,
        workers: int = 1,
    ) -> None:
        super().__init__(
            name=TRANSLATION_QUEUE_NAME,
            logger=logger,
            handler=TranslationHandler(
                logger,
                translation_repository,
                translation_result_repository,
                novel_chapter_repository,
                realtime_hub,
                translation_service_provider_factory,
            ),
            workers=workers,
        )


def build_translation_event(
    translation: Translation,
    task: TranslationTask,
    *,
    refetch: bool,
) -> dict[str, Any]:
    """Build one versioned queue event for a translation task."""

    return {
        "schemaVersion": TRANSLATION_EVENT_SCHEMA_VERSION,
        "type": TRANSLATION_EVENT_TYPE,
        "translationId": translation.id,
        "createdBy": translation.created_by,
        "taskId": task.id,
        "refetch": refetch,
        "enqueuedAt": datetime.now(UTC).isoformat(),
    }


def build_translation_updated_payload(
    translation: Translation,
    *,
    task_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "translationId": translation.id,
        "status": translation.status.value,
        "updatedAt": translation.updated_at.isoformat(),
        "progress": {
            "total": translation.progress.total,
            "created": translation.progress.created,
            "queued": translation.progress.queued,
            "running": translation.progress.running,
            "completed": translation.progress.completed,
            "failed": translation.progress.failed,
        },
    }
    if task_id is not None:
        payload["taskId"] = task_id
    return payload


def _required_string(content: Mapping[str, Any], key: str) -> str:
    value = content.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing translation event field: {key}")
    return value


def _find_task(translation: Translation, task_id: str) -> TranslationTask | None:
    return next((item for item in translation.tasks if item.id == task_id), None)


def _require_task(translation: Translation, task_id: str) -> TranslationTask:
    task = _find_task(translation, task_id)
    if task is None:
        raise TranslationNotFoundError
    return task
