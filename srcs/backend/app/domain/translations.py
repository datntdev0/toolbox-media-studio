"""Translation project domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.novels import Novel


class TranslationStatus(StrEnum):
    """Translation lifecycle and processing states."""

    NEEDS_SETUP = "needs_setup"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"
    DELETED = "deleted"


@dataclass(slots=True)
class TranslationConfiguration:
    """AI configuration persisted with a translation project."""

    provider_id: str
    model_id: str
    global_prompt: str


@dataclass(slots=True)
class Translation:
    """Persisted translation project."""

    id: str
    name: str
    novel_id: str
    target_language: str
    configuration: TranslationConfiguration | None
    status: TranslationStatus
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    etag: str | None = None


@dataclass(slots=True)
class TranslationPage:
    """Paged translation list result."""

    items: list[Translation]
    continuation_token: str | None


@dataclass(slots=True)
class TranslationView:
    """Translation project enriched with its current novel."""

    translation: Translation
    novel: Novel | None


@dataclass(slots=True)
class TranslationViewPage:
    """Paged enriched translation list."""

    items: list[TranslationView]
    continuation_token: str | None
