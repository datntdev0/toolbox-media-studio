"""Outbound response models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.jobs import JobKind, JobStatus
from app.domain.novels import Novel, NovelStatus
from app.domain.users import User, UserRole, UserStatus


class TokenResponse(BaseModel):
    """Issued on successful login."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User payload returned by auth and user-management endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    email: str
    display_name: str | None = Field(default=None, alias="displayName")
    role: UserRole
    status: UserStatus
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    etag: str | None = None


class UserListResponse(BaseModel):
    """Paged response for listing users."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[UserResponse]
    continuation_token: str | None = Field(default=None, alias="continuationToken")


class NovelResponse(BaseModel):
    """Novel payload returned by novel-management endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    description: str | None = None
    cover_image_url: str | None = Field(default=None, alias="coverImageUrl")
    language: str | None = None
    author: str | None = None
    tags: list[str]
    notes: str | None = None
    status: NovelStatus
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    etag: str | None = None


class NovelListResponse(BaseModel):
    """Paged response for listing novels."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[NovelResponse]
    continuation_token: str | None = Field(default=None, alias="continuationToken")


class CrawlerJobResponse(BaseModel):
    """Crawler job payload returned by the crawler-job endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    kind: JobKind
    crawler_id: str = Field(alias="crawlerId")
    url: str
    status: JobStatus
    attempts: int
    reused: bool
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


def to_user_response(current_user: User) -> UserResponse:
    """Convert a User domain model to a UserResponse model."""

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        role=current_user.role,
        status=current_user.status,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        etag=current_user.etag,
    )


def to_novel_response(novel: Novel) -> NovelResponse:
    """Convert a Novel domain model to a NovelResponse model."""

    return NovelResponse(
        id=novel.id,
        title=novel.title,
        description=novel.description,
        cover_image_url=novel.cover_image_url,
        language=novel.language,
        author=novel.author,
        tags=novel.tags,
        notes=novel.notes,
        status=novel.status,
        created_at=novel.created_at,
        updated_at=novel.updated_at,
        etag=novel.etag,
    )
