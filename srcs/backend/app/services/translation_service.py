"""Application service for translation projects."""

from datetime import UTC, datetime

from app.domain.novels import Novel, NovelChapter
from app.domain.translations import (
    Translation,
    TranslationConfiguration,
    TranslationProgress,
    TranslationStatus,
    TranslationSyncChanges,
    TranslationSyncResult,
    TranslationTask,
    TranslationTaskStatus,
    TranslationView,
    TranslationViewPage,
)
from app.repositories.novel_chapter_repository import NovelChapterRepository
from app.repositories.novel_repository import NovelNotFoundError, NovelRepository
from app.repositories.translation_repository import (
    TranslationConflictError,
    TranslationNotFoundError,
    TranslationRepository,
    reconcile_translation_status,
)
from app.repositories.translation_result_repository import TranslationResultRepository


class TranslationNovelNotFoundError(Exception):
    """Raised when a translation references an unknown novel."""


class TranslationSyncConflictError(Exception):
    """Raised when a translation manifest cannot be synchronized."""


class TranslationResultDeleteError(Exception):
    """Raised when translated content cannot be deleted safely."""


class TranslationService:
    """Coordinate translation persistence and live novel resolution."""

    def __init__(
        self,
        translation_repository: TranslationRepository,
        novel_repository: NovelRepository,
        novel_chapter_repository: NovelChapterRepository | None = None,
        translation_result_repository: TranslationResultRepository | None = None,
    ) -> None:
        self._translations = translation_repository
        self._novels = novel_repository
        self._chapters = novel_chapter_repository
        self._results = translation_result_repository

    def create(self, translation: Translation) -> TranslationView:
        novel = self._require_novel(translation.novel_id)
        if self._chapters is not None:
            translation.tasks = [
                _task_from_chapter(chapter)
                for chapter in self._chapters.list(novel.id).items
                if not chapter.source_removed
            ]
            translation.progress = TranslationProgress.from_tasks(translation.tasks)
        created = self._translations.create(translation)
        return TranslationView(translation=created, novel=novel)

    def list(self, limit: int, continuation_token: str | None) -> TranslationViewPage:
        page = self._translations.list(limit, continuation_token)
        return TranslationViewPage(
            items=[
                TranslationView(
                    translation=translation,
                    novel=self._find_novel(translation.novel_id),
                )
                for translation in page.items
            ],
            continuation_token=page.continuation_token,
        )

    def get_by_id(self, id: str) -> TranslationView | None:
        translation = self._translations.get_by_id(id)
        if translation is None:
            return None
        return TranslationView(
            translation=translation,
            novel=self._find_novel(translation.novel_id),
        )

    def update(
        self,
        id: str,
        *,
        name: str,
        novel_id: str,
        target_language: str,
        configuration: TranslationConfiguration | None,
        etag: str | None,
        updated_by: str,
    ) -> TranslationView:
        translation = self._translations.get_by_id(id)
        if translation is None:
            raise TranslationNotFoundError

        novel = self._require_novel(novel_id)

        if novel_id != translation.novel_id:
            active = any(
                task.status in {TranslationTaskStatus.QUEUED, TranslationTaskStatus.RUNNING}
                or task.result_available
                for task in translation.tasks
            )
            if active:
                raise TranslationSyncConflictError(
                    "Translation novel cannot change after processing has started"
                )
            translation.tasks = (
                [
                    _task_from_chapter(chapter)
                    for chapter in self._chapters.list(novel_id).items
                    if not chapter.source_removed
                ]
                if self._chapters is not None
                else []
            )
            translation.progress = TranslationProgress.from_tasks(translation.tasks)

        translation.name = name.strip()
        translation.novel_id = novel_id
        translation.target_language = target_language.strip()
        translation.configuration = configuration
        translation.updated_at = datetime.now(UTC)
        translation.updated_by = updated_by
        if translation.status == TranslationStatus.NEEDS_SETUP and configuration is not None:
            translation.status = TranslationStatus.READY
        elif translation.status == TranslationStatus.READY and configuration is None:
            translation.status = TranslationStatus.NEEDS_SETUP

        updated = self._translations.update(translation, etag)
        return TranslationView(translation=updated, novel=novel)

    def delete(self, id: str, deleted_by: str) -> None:
        translation = self._translations.get_by_id(id)
        if translation is None:
            raise TranslationNotFoundError
        if self._results is not None:
            try:
                self._results.delete_by_translation(id)
            except Exception as exc:
                raise TranslationResultDeleteError from exc
        self._translations.delete(id, etag=None, deleted_by=deleted_by)

    def sync(self, id: str, *, updated_by: str) -> TranslationSyncResult:
        if self._chapters is None:
            raise TranslationSyncConflictError("Novel chapter repository is unavailable")

        for _ in range(3):
            translation = self._translations.get_by_id(id)
            if translation is None:
                raise TranslationNotFoundError
            novel = self._require_novel(translation.novel_id)

            chapters = [
                chapter
                for chapter in self._chapters.list(novel.id).items
                if not chapter.source_removed
            ]
            changes = _synchronize_tasks(translation, chapters)
            translation.progress = TranslationProgress.from_tasks(translation.tasks)
            translation.updated_by = updated_by
            translation.updated_at = datetime.now(UTC)
            translation.status = reconcile_translation_status(translation)
            try:
                updated = self._translations.update(translation, translation.etag)
            except TranslationConflictError:
                continue
            return TranslationSyncResult(
                view=TranslationView(translation=updated, novel=novel),
                changes=changes,
            )
        raise TranslationSyncConflictError("Translation has changed")

    def _find_novel(self, novel_id: str) -> Novel | None:
        try:
            return self._novels.get_by_id(novel_id)
        except NovelNotFoundError:
            return None

    def _require_novel(self, novel_id: str) -> Novel:
        novel = self._find_novel(novel_id)
        if novel is None:
            raise TranslationNovelNotFoundError
        return novel


def _task_from_chapter(chapter: NovelChapter) -> TranslationTask:
    return TranslationTask(
        id=chapter.id,
        title=chapter.title,
        chapter_number=chapter.chapter_number,
        manifest_index=chapter.manifest_index,
        source_chapter_updated_at=chapter.updated_at,
    )


def _synchronize_tasks(
    translation: Translation,
    chapters: list[NovelChapter],
) -> TranslationSyncChanges:
    current = {task.id: task for task in translation.tasks}
    active_ids: set[str] = set()
    added = refreshed = preserved = removed = 0

    for chapter in sorted(chapters, key=lambda item: (item.manifest_index, item.id)):
        active_ids.add(chapter.id)
        task = current.get(chapter.id)
        if task is None:
            translation.tasks.append(_task_from_chapter(chapter))
            added += 1
            continue

        metadata_changed = (
            task.title != chapter.title
            or task.chapter_number != chapter.chapter_number
            or task.manifest_index != chapter.manifest_index
            or task.source_removed
        )
        source_is_newer = chapter.updated_at > task.source_chapter_updated_at
        task.title = chapter.title
        task.chapter_number = chapter.chapter_number
        task.manifest_index = chapter.manifest_index
        task.source_removed = False
        if source_is_newer and task.result_available:
            task.source_updated = True
            task.source_chapter_updated_at = chapter.updated_at
            preserved += 1
        elif source_is_newer or metadata_changed:
            task.source_chapter_updated_at = chapter.updated_at
            refreshed += 1

    for task in translation.tasks:
        if task.id in active_ids or task.source_removed:
            continue
        task.source_removed = True
        if task.status == TranslationTaskStatus.QUEUED:
            task.status = TranslationTaskStatus.CREATED
        removed += 1

    translation.tasks.sort(key=lambda item: (item.manifest_index, item.id))
    return TranslationSyncChanges(
        added=added,
        refreshed=refreshed,
        preserved=preserved,
        removed=removed,
    )
