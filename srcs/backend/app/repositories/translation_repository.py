"""Translation repository contract and in-memory implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Protocol

from app.domain.translations import Translation, TranslationPage, TranslationStatus


class TranslationRepository(Protocol):
    """Persistence contract for translation projects."""

    def create(self, translation: Translation) -> Translation: ...

    def get_by_id(self, id: str) -> Translation | None: ...

    def list(self, limit: int, continuation_token: str | None) -> TranslationPage: ...

    def update(self, translation: Translation, etag: str | None) -> Translation: ...

    def delete(self, id: str, etag: str | None, deleted_by: str) -> None: ...


class TranslationNotFoundError(Exception):
    """Raised when a translation cannot be found."""


class TranslationConflictError(Exception):
    """Raised when optimistic concurrency validation fails."""


class TranslationContinuationTokenError(ValueError):
    """Raised when an in-memory continuation token is invalid."""


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

    @staticmethod
    def _next_etag() -> str:
        return datetime.now(UTC).isoformat()
