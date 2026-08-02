"""Novel domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


@dataclass(slots=True)
class NovelBinding:
    """Novel-specific relationship to a scraping source."""

    scraping_id: str
    bound_at: datetime
    last_synced_at: datetime


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
    binding: NovelBinding | None = None
    chapter_count: int = 0
    created_by: str | None = None
    created_at: datetime | None = None
    updated_by: str | None = None
    updated_at: datetime | None = None
    deleted_by: str | None = None
    deleted_at: datetime | None = None
    etag: str | None = None


@dataclass(slots=True)
class NovelPage:
    """Paged novel list result."""

    items: list[Novel]
    continuation_token: str | None


@dataclass(slots=True)
class NovelChapter:
    """One chapter cloned from a scraping manifest into a novel."""

    id: str
    novel_id: str
    scraping_task_id: str
    title: str
    chapter_number: int | None
    manifest_index: int
    source_url: str
    content: list[str]
    content_available: bool
    manually_edited: bool
    source_updated: bool
    source_removed: bool
    source_result_updated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    updated_by: str | None = None
    etag: str | None = None


@dataclass(slots=True)
class NovelChapterPage:
    """Ordered chapters belonging to a novel."""

    items: list[NovelChapter]


@dataclass(frozen=True, slots=True)
class NovelSyncResult:
    """Change summary returned by bind and sync."""

    novel: Novel
    chapters: list[NovelChapter]
    added: int
    refreshed: int
    preserved: int
    removed: int


class NovelBindRequest(BaseModel):
    """Scraping selection accepted by the bind endpoint."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    scraping_id: str = Field(min_length=1, alias="scrapingId")


class NovelChapterUpdateRequest(BaseModel):
    """Editable chapter content with optimistic concurrency."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    content: str
    etag: str
