"""Application service for translation projects."""

from datetime import UTC, datetime

from app.domain.translations import (
    Translation,
    TranslationConfiguration,
    TranslationStatus,
    TranslationView,
    TranslationViewPage,
)
from app.repositories.novel_repository import NovelRepository
from app.repositories.translation_repository import (
    TranslationNotFoundError,
    TranslationRepository,
)


class TranslationNovelNotFoundError(Exception):
    """Raised when a translation references an unknown novel."""


class TranslationService:
    """Coordinate translation persistence and live novel resolution."""

    def __init__(
        self,
        translation_repository: TranslationRepository,
        novel_repository: NovelRepository,
    ) -> None:
        self._translations = translation_repository
        self._novels = novel_repository

    def create(self, translation: Translation) -> TranslationView:
        novel = self._novels.get_by_id(translation.novel_id)
        if novel is None:
            raise TranslationNovelNotFoundError
        created = self._translations.create(translation)
        return TranslationView(translation=created, novel=novel)

    def list(self, limit: int, continuation_token: str | None) -> TranslationViewPage:
        page = self._translations.list(limit, continuation_token)
        return TranslationViewPage(
            items=[
                TranslationView(
                    translation=translation,
                    novel=self._novels.get_by_id(translation.novel_id),
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
            novel=self._novels.get_by_id(translation.novel_id),
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

        novel = self._novels.get_by_id(novel_id)
        if novel is None:
            raise TranslationNovelNotFoundError

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
        self._translations.delete(id, etag=None, deleted_by=deleted_by)
