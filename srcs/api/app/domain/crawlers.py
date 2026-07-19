"""Crawler domain and response models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True, slots=True)
class CrawlerSource:
    """Validated crawler source URL."""

    crawler_id: str
    source_url: str
    canonical_url: str
    source_novel_id: str


class CrawlerSummaryResponse(BaseModel):
    """Available crawler summary."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    hosts: tuple[str, ...]
    metadata_supported: bool = Field(alias="metadataSupported")


class CrawlerListResponse(BaseModel):
    """Available crawler registry response."""

    items: list[CrawlerSummaryResponse]


class CrawlerChapterResponse(BaseModel):
    """Chapter metadata returned by the crawler endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    title: str
    url: str
    chapter_number: int | None = Field(default=None, alias="chapterNumber")


class CrawlerMetadataResponse(BaseModel):
    """Novel metadata returned by a crawler."""

    model_config = ConfigDict(populate_by_name=True)

    crawler_id: str = Field(alias="crawlerId")
    source_url: str = Field(alias="sourceUrl")
    source_novel_id: str = Field(alias="sourceNovelId")
    title: str
    author: str | None = None
    category: str | None = None
    updated_date: str | None = Field(default=None, alias="updatedDate")
    protagonists: list[str]
    description: str | None = None
    cover_image_url: str | None = Field(default=None, alias="coverImageUrl")
    chapters: list[CrawlerChapterResponse]
    cached: bool
    fetched_at: datetime = Field(alias="fetchedAt")


class CrawlerChapterContentResponse(BaseModel):
    """Chapter content returned by the crawler endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    crawler_id: str = Field(alias="crawlerId")
    novel_url: str = Field(alias="novelUrl")
    chapter_url: str = Field(alias="chapterUrl")
    chapter_title: str = Field(alias="chapterTitle")
    chapter_number: int | None = Field(default=None, alias="chapterNumber")
    content: list[str]
    cached: bool
    fetched_at: datetime = Field(alias="fetchedAt")
