"""Outbound response models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.novels import Novel, NovelBinding, NovelChapter, NovelStatus, NovelSyncResult
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
    chapter_count: int = Field(default=0, alias="chapterCount")
    binding: "NovelBindingResponse | None" = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    etag: str | None = None


class NovelListResponse(BaseModel):
    """Paged response for listing novels."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[NovelResponse]
    continuation_token: str | None = Field(default=None, alias="continuationToken")


class NovelBindingResponse(BaseModel):
    """Novel-specific relationship to a scraping source."""

    model_config = ConfigDict(populate_by_name=True)

    scraping_id: str = Field(alias="scrapingId")
    bound_at: datetime = Field(alias="boundAt")
    last_synced_at: datetime = Field(alias="lastSyncedAt")


class NovelChapterSummaryResponse(BaseModel):
    """Chapter metadata included in a novel detail response."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    chapter_number: int | None = Field(default=None, alias="chapterNumber")
    manifest_index: int = Field(alias="manifestIndex")
    content_available: bool = Field(alias="contentAvailable")
    manually_edited: bool = Field(alias="manuallyEdited")
    source_updated: bool = Field(alias="sourceUpdated")
    source_removed: bool = Field(alias="sourceRemoved")
    updated_at: datetime = Field(alias="updatedAt")
    etag: str | None = None


class NovelDetailResponse(NovelResponse):
    """Novel information with its ordered chapter manifest."""

    chapters: list[NovelChapterSummaryResponse] = Field(default_factory=list)


class NovelChapterContentResponse(NovelChapterSummaryResponse):
    """One chapter with content represented as readable paragraphs."""

    content: list[str] = Field(default_factory=list)


class NovelSyncChangesResponse(BaseModel):
    """Counters describing the result of binding or synchronizing."""

    added: int
    refreshed: int
    preserved: int
    removed: int


class NovelSyncResponse(BaseModel):
    """Updated novel and chapter state after bind or sync."""

    novel: NovelDetailResponse
    changes: NovelSyncChangesResponse


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
        chapter_count=novel.chapter_count,
        binding=to_novel_binding_response(novel.binding),
        created_at=novel.created_at,
        updated_at=novel.updated_at,
        etag=novel.etag,
    )


def to_novel_binding_response(
    binding: NovelBinding | None,
) -> NovelBindingResponse | None:
    if binding is None:
        return None
    return NovelBindingResponse(
        scraping_id=binding.scraping_id,
        bound_at=binding.bound_at,
        last_synced_at=binding.last_synced_at,
    )


def to_novel_chapter_summary(
    chapter: NovelChapter,
) -> NovelChapterSummaryResponse:
    return NovelChapterSummaryResponse(
        id=chapter.id,
        title=chapter.title,
        chapter_number=chapter.chapter_number,
        manifest_index=chapter.manifest_index,
        content_available=chapter.content_available,
        manually_edited=chapter.manually_edited,
        source_updated=chapter.source_updated,
        source_removed=chapter.source_removed,
        updated_at=chapter.updated_at,
        etag=chapter.etag,
    )


def to_novel_detail_response(
    novel: Novel,
    chapters: list[NovelChapter],
) -> NovelDetailResponse:
    return NovelDetailResponse(
        **to_novel_response(novel).model_dump(),
        chapters=[to_novel_chapter_summary(chapter) for chapter in chapters],
    )


def to_novel_sync_response(result: NovelSyncResult) -> NovelSyncResponse:
    return NovelSyncResponse(
        novel=to_novel_detail_response(result.novel, result.chapters),
        changes=NovelSyncChangesResponse(
            added=result.added,
            refreshed=result.refreshed,
            preserved=result.preserved,
            removed=result.removed,
        ),
    )


# NovelResponse intentionally appears before the binding contract so existing
# response definitions stay grouped; resolve that forward reference explicitly.
NovelResponse.model_rebuild()
