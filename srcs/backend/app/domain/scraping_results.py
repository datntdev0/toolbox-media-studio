"""Scraping task result domain models and API contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


@dataclass(slots=True)
class ScrapingResult:
    """Persisted output for one embedded scraping task."""

    id: str
    scraping_id: str
    task_id: str
    title: str
    chapter_number: int | None
    content: list[str]
    created_at: datetime
    updated_at: datetime
    etag: str | None = None


class ScrapingResultResponse(BaseModel):
    """One task result returned by the API."""

    model_config = ConfigDict(populate_by_name=True)

    scraping_id: str = Field(alias="scrapingId")
    task_id: str = Field(alias="taskId")
    title: str
    chapter_number: int | None = Field(default=None, alias="chapterNumber")
    content: list[str] = Field(default_factory=list)
    created_at: datetime = Field(alias="createdAt")


def to_scraping_result_response(result: ScrapingResult) -> ScrapingResultResponse:
    return ScrapingResultResponse(
        scraping_id=result.scraping_id,
        task_id=result.task_id,
        title=result.title,
        chapter_number=result.chapter_number,
        content=result.content,
        created_at=result.created_at,
    )
