"""Novel domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NovelStatus(StrEnum):
    """Supported novel lifecycle states."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass(slots=True)
class Novel:
    """Persisted novel record."""

    id: str
    title: str
    description: str | None
    cover_image_url: str | None
    language: str | None
    author: str | None
    tags: list[str]
    notes: str | None
    status: NovelStatus
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    etag: str | None = None


@dataclass(slots=True)
class NovelPage:
    """Paged novel list result."""

    items: list[Novel]
    continuation_token: str | None
