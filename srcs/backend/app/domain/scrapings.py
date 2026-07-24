"""Scraping domain models and API contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScrapingTaskStatus(StrEnum):
    """Embedded scraping task lifecycle states."""

    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in {ScrapingTaskStatus.COMPLETED, ScrapingTaskStatus.FAILED}


@dataclass(slots=True)
class ScrapingMetadata:
    """Trusted novel metadata captured from a crawler."""

    source_novel_id: str
    title: str
    author: str | None
    category: str | None
    updated_date: str | None
    protagonists: list[str]
    description: str | None
    cover_image_url: str | None
    fetched_at: datetime


@dataclass(slots=True)
class ScrapingTask:
    """One chapter task embedded in a Scraping document."""

    id: str
    source_url: str
    title: str
    chapter_number: int | None
    manifest_index: int
    status: ScrapingTaskStatus = ScrapingTaskStatus.CREATED
    attempts: int = 0
    last_error: str | None = None
    result_available: bool = False
    completed_at: datetime | None = None


@dataclass(slots=True)
class ScrapingProgress:
    """Rollup counters stored with a Scraping."""

    total: int
    created: int
    queued: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0

    @classmethod
    def from_tasks(cls, tasks: list[ScrapingTask]) -> ScrapingProgress:
        counts = {status: 0 for status in ScrapingTaskStatus}
        for task in tasks:
            counts[task.status] += 1
        return cls(
            total=len(tasks),
            created=counts[ScrapingTaskStatus.CREATED],
            queued=counts[ScrapingTaskStatus.QUEUED],
            running=counts[ScrapingTaskStatus.RUNNING],
            completed=counts[ScrapingTaskStatus.COMPLETED],
            failed=counts[ScrapingTaskStatus.FAILED],
        )


@dataclass(slots=True)
class Scraping:
    """Persisted scraping with an embedded chapter task manifest."""

    id: str
    crawler_id: str
    source_url: str
    metadata: ScrapingMetadata
    tasks: list[ScrapingTask]
    progress: ScrapingProgress
    idempotency_key: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    etag: str | None = None


@dataclass(frozen=True, slots=True)
class ScrapingCreateResult:
    """Result of an idempotent create-or-return operation."""

    scraping: Scraping
    created: bool


@dataclass(frozen=True, slots=True)
class ScrapingQueueResult:
    """Result of queueing a chapter-number range."""

    scraping: Scraping
    tasks: list[ScrapingTask]


@dataclass(slots=True)
class ScrapingPage:
    """Paged scraping repository result."""

    items: list[Scraping]
    continuation_token: str | None


class ScrapingCreateRequest(BaseModel):
    """Request accepted by POST /api/scrapings."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    crawler_id: str = Field(min_length=1, alias="crawlerId")
    source_url: str = Field(min_length=1, alias="sourceUrl")


class ScrapingStartRequest(BaseModel):
    """Task range accepted by PATCH /api/scrapings/{id}/start."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    chapter_from: int = Field(ge=1, alias="chapterFrom")
    chapter_to: int = Field(ge=1, alias="chapterTo")
    refetch: bool = False
    force: bool = False

    @model_validator(mode="after")
    def validate_chapter_range(self) -> ScrapingStartRequest:
        if self.chapter_from > self.chapter_to:
            raise ValueError("chapterFrom must be less than or equal to chapterTo")
        return self


class ScrapingProgressResponse(BaseModel):
    """Task progress returned with a Scraping."""

    total: int
    created: int
    queued: int
    running: int
    completed: int
    failed: int


class ScrapingSummaryResponse(BaseModel):
    """Scraping list item."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    crawler_id: str = Field(alias="crawlerId")
    source_url: str = Field(alias="sourceUrl")
    title: str
    cover_image_url: str | None = Field(default=None, alias="coverImageUrl")
    progress: ScrapingProgressResponse
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ScrapingCreateResponse(ScrapingSummaryResponse):
    """Response returned after accepting a scraping."""

    reused: bool


class ScrapingMetadataResponse(BaseModel):
    """Novel metadata stored with a scraping."""

    model_config = ConfigDict(populate_by_name=True)

    source_novel_id: str = Field(alias="sourceNovelId")
    title: str
    author: str | None = None
    category: str | None = None
    updated_date: str | None = Field(default=None, alias="updatedDate")
    protagonists: list[str] = Field(default_factory=list)
    description: str | None = None
    cover_image_url: str | None = Field(default=None, alias="coverImageUrl")
    fetched_at: datetime = Field(alias="fetchedAt")


class ScrapingTaskResponse(BaseModel):
    """Public embedded scraping task."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    chapter_number: int | None = Field(default=None, alias="chapterNumber")
    manifest_index: int = Field(alias="manifestIndex")
    status: ScrapingTaskStatus
    attempts: int
    last_error: str | None = Field(default=None, alias="lastError")
    result_available: bool = Field(alias="resultAvailable")
    completed_at: datetime | None = Field(default=None, alias="completedAt")


class ScrapingDetailResponse(BaseModel):
    """Scraping detail returned to the master-detail UI."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    crawler_id: str = Field(alias="crawlerId")
    source_url: str = Field(alias="sourceUrl")
    metadata: ScrapingMetadataResponse
    progress: ScrapingProgressResponse
    tasks: list[ScrapingTaskResponse] = Field(default_factory=list)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ScrapingListResponse(BaseModel):
    """Paged scraping list response."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[ScrapingSummaryResponse] = Field(default_factory=list)
    continuation_token: str | None = Field(default=None, alias="continuationToken")


def to_scraping_summary(scraping: Scraping) -> ScrapingSummaryResponse:
    return ScrapingSummaryResponse(
        id=scraping.id,
        crawler_id=scraping.crawler_id,
        source_url=scraping.source_url,
        title=scraping.metadata.title,
        cover_image_url=scraping.metadata.cover_image_url,
        progress=ScrapingProgressResponse(
            total=scraping.progress.total,
            created=scraping.progress.created,
            queued=scraping.progress.queued,
            running=scraping.progress.running,
            completed=scraping.progress.completed,
            failed=scraping.progress.failed,
        ),
        created_at=scraping.created_at,
        updated_at=scraping.updated_at,
    )


def to_scraping_detail(scraping: Scraping) -> ScrapingDetailResponse:
    metadata = scraping.metadata
    progress = scraping.progress
    return ScrapingDetailResponse(
        id=scraping.id,
        crawler_id=scraping.crawler_id,
        source_url=scraping.source_url,
        metadata=ScrapingMetadataResponse(
            source_novel_id=metadata.source_novel_id,
            title=metadata.title,
            author=metadata.author,
            category=metadata.category,
            updated_date=metadata.updated_date,
            protagonists=metadata.protagonists,
            description=metadata.description,
            cover_image_url=metadata.cover_image_url,
            fetched_at=metadata.fetched_at,
        ),
        progress=ScrapingProgressResponse(
            total=progress.total,
            created=progress.created,
            queued=progress.queued,
            running=progress.running,
            completed=progress.completed,
            failed=progress.failed,
        ),
        tasks=[
            ScrapingTaskResponse(
                id=task.id,
                title=task.title,
                chapter_number=task.chapter_number,
                manifest_index=task.manifest_index,
                status=task.status,
                attempts=task.attempts,
                last_error=task.last_error,
                result_available=task.result_available,
                completed_at=task.completed_at,
            )
            for task in scraping.tasks
        ],
        created_at=scraping.created_at,
        updated_at=scraping.updated_at,
    )
