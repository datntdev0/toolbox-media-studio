"""Scraping domain models and API contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ScrapingStatus(StrEnum):
    """Scraping lifecycle states."""

    QUEUED = "queued"
    PROCESSING = "processing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in {ScrapingStatus.COMPLETED, ScrapingStatus.FAILED}

    @property
    def is_active(self) -> bool:
        return not self.is_terminal


class ScrapingTaskStatus(StrEnum):
    """Embedded scraping task lifecycle states."""

    PENDING = "pending"
    PROCESSING = "processing"
    RETRYING = "retrying"
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
    status: ScrapingTaskStatus = ScrapingTaskStatus.PENDING
    attempts: int = 0
    last_error: str | None = None
    result_available: bool = False
    completed_at: datetime | None = None


@dataclass(slots=True)
class ScrapingProgress:
    """Rollup counters stored with a Scraping."""

    total: int
    pending: int
    processing: int = 0
    retrying: int = 0
    completed: int = 0
    failed: int = 0

    @classmethod
    def from_tasks(cls, tasks: list[ScrapingTask]) -> ScrapingProgress:
        counts = {status: 0 for status in ScrapingTaskStatus}
        for task in tasks:
            counts[task.status] += 1
        return cls(
            total=len(tasks),
            pending=counts[ScrapingTaskStatus.PENDING],
            processing=counts[ScrapingTaskStatus.PROCESSING],
            retrying=counts[ScrapingTaskStatus.RETRYING],
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
    status: ScrapingStatus
    tasks: list[ScrapingTask]
    progress: ScrapingProgress
    attempts: int
    last_error: str | None
    idempotency_key: str
    active_key: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    etag: str | None = None


@dataclass(frozen=True, slots=True)
class ScrapingCreateResult:
    """Result of an idempotent create-or-return operation."""

    scraping: Scraping
    created: bool


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


class ScrapingProgressSummaryResponse(BaseModel):
    """Compact progress returned in list/create responses."""

    total: int
    completed: int
    failed: int


class ScrapingProgressResponse(ScrapingProgressSummaryResponse):
    """Complete progress returned by the detail endpoint."""

    pending: int
    processing: int
    retrying: int


class ScrapingSummaryResponse(BaseModel):
    """Scraping list item."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    crawler_id: str = Field(alias="crawlerId")
    source_url: str = Field(alias="sourceUrl")
    title: str
    cover_image_url: str | None = Field(default=None, alias="coverImageUrl")
    status: ScrapingStatus
    progress: ScrapingProgressSummaryResponse
    attempts: int
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
    result_available: bool = Field(alias="resultAvailable")
    completed_at: datetime | None = Field(default=None, alias="completedAt")


class ScrapingDetailResponse(BaseModel):
    """Scraping detail returned to the master-detail UI."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    crawler_id: str = Field(alias="crawlerId")
    source_url: str = Field(alias="sourceUrl")
    status: ScrapingStatus
    metadata: ScrapingMetadataResponse
    progress: ScrapingProgressResponse
    tasks: list[ScrapingTaskResponse] = Field(default_factory=list)
    attempts: int
    last_error: str | None = Field(default=None, alias="lastError")
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
        status=scraping.status,
        progress=ScrapingProgressSummaryResponse(
            total=scraping.progress.total,
            completed=scraping.progress.completed,
            failed=scraping.progress.failed,
        ),
        attempts=scraping.attempts,
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
        status=scraping.status,
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
            pending=progress.pending,
            processing=progress.processing,
            retrying=progress.retrying,
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
                result_available=task.result_available,
                completed_at=task.completed_at,
            )
            for task in scraping.tasks
        ],
        attempts=scraping.attempts,
        last_error=scraping.last_error,
        created_at=scraping.created_at,
        updated_at=scraping.updated_at,
    )
