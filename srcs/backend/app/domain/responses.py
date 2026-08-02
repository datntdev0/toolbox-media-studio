"""Outbound response models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.novels import Novel, NovelBinding, NovelChapter, NovelSyncResult
from app.domain.translations import (
    TranslationConfiguration,
    TranslationProgress,
    TranslationStatus,
    TranslationSyncResult,
    TranslationTask,
    TranslationTaskStatus,
    TranslationView,
)
from app.domain.users import User, UserRole, UserStatus
from app.domain.workspace_results import WorkspaceResult
from app.domain.workspaces import (
    WorkspaceProgress,
    WorkspaceSourceType,
    WorkspaceTask,
    WorkspaceTaskStatus,
    WorkspaceType,
    WorkspaceView,
)


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


class NovelLanguageResponse(BaseModel):
    """One original or translated language available for a novel."""

    model_config = ConfigDict(populate_by_name=True)

    code: str
    source_type: WorkspaceSourceType = Field(alias="sourceType")


class NovelLanguageListResponse(BaseModel):
    """All unique languages currently available for a novel."""

    items: list[NovelLanguageResponse]


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


class TranslationConfigurationResponse(BaseModel):
    """Persisted AI configuration for a translation."""

    model_config = ConfigDict(populate_by_name=True)

    provider_id: str = Field(alias="providerId")
    model_id: str = Field(alias="modelId")
    global_prompt: str = Field(alias="globalPrompt")


class TranslationResponse(BaseModel):
    """Translation payload enriched with the current bound novel."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    novel_id: str = Field(alias="novelId")
    target_language: str = Field(alias="targetLanguage")
    configuration: TranslationConfigurationResponse | None = None
    status: TranslationStatus
    novel: NovelResponse | None = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    etag: str | None = None


class TranslationProgressResponse(BaseModel):
    """Translation task rollup."""

    total: int
    created: int
    queued: int
    running: int
    completed: int
    failed: int


class TranslationTaskResponse(BaseModel):
    """One embedded translation task."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    chapter_number: int | None = Field(default=None, alias="chapterNumber")
    manifest_index: int = Field(alias="manifestIndex")
    status: TranslationTaskStatus
    attempts: int
    last_error: str | None = Field(default=None, alias="lastError")
    result_available: bool = Field(alias="resultAvailable")
    completed_at: datetime | None = Field(default=None, alias="completedAt")
    source_chapter_updated_at: datetime = Field(alias="sourceChapterUpdatedAt")
    source_updated: bool = Field(alias="sourceUpdated")
    source_removed: bool = Field(alias="sourceRemoved")


class TranslationDetailResponse(TranslationResponse):
    """Translation information with its task manifest."""

    progress: TranslationProgressResponse
    tasks: list[TranslationTaskResponse] = Field(default_factory=list)


class TranslationSyncChangesResponse(BaseModel):
    """Task manifest changes returned by translation sync."""

    added: int
    refreshed: int
    preserved: int
    removed: int


class TranslationSyncResponse(BaseModel):
    """Translation sync result."""

    translation: TranslationDetailResponse
    changes: TranslationSyncChangesResponse


class TranslationListResponse(BaseModel):
    """Paged translation list response."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[TranslationResponse]
    continuation_token: str | None = Field(default=None, alias="continuationToken")


class WorkspaceResponse(BaseModel):
    """Workspace payload enriched with live novel metadata."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    type: WorkspaceType
    novel_id: str = Field(alias="novelId")
    language: str
    source_type: WorkspaceSourceType = Field(alias="sourceType")
    source_available: bool = Field(alias="sourceAvailable")
    chapter_count: int = Field(alias="chapterCount")
    novel: NovelResponse | None = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    etag: str | None = None


class WorkspaceDetailResponse(WorkspaceResponse):
    """Workspace payload including language-aware chapters."""

    chapters: list[NovelChapterSummaryResponse] = Field(default_factory=list)
    progress: "WorkspaceProgressResponse"
    tasks: list["WorkspaceTaskResponse"] = Field(default_factory=list)


class WorkspaceProgressResponse(BaseModel):
    """Workspace task rollup counters."""

    total: int
    created: int
    queued: int
    running: int
    completed: int
    failed: int


class WorkspaceTaskResponse(BaseModel):
    """One persisted workspace chapter task."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    chapter_number: int | None = Field(default=None, alias="chapterNumber")
    manifest_index: int = Field(alias="manifestIndex")
    status: WorkspaceTaskStatus
    attempts: int
    last_error: str | None = Field(default=None, alias="lastError")
    result_available: bool = Field(alias="resultAvailable")
    completed_at: datetime | None = Field(default=None, alias="completedAt")
    source_chapter_updated_at: datetime = Field(alias="sourceChapterUpdatedAt")
    source_updated: bool = Field(alias="sourceUpdated")
    source_removed: bool = Field(alias="sourceRemoved")
    provider: str | None = None
    voice: str | None = None


class WorkspaceListResponse(BaseModel):
    """Paged workspace list."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[WorkspaceResponse]
    continuation_token: str | None = Field(default=None, alias="continuationToken")


class WorkspaceTaskResultSentenceResponse(BaseModel):
    """One sentence audio file in a completed workspace task result."""

    model_config = ConfigDict(populate_by_name=True)

    index: int
    audio_url: str = Field(alias="audioUrl")


class WorkspaceTaskResultResponse(BaseModel):
    """Completed audio output for one workspace chapter task."""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    workspace_id: str = Field(alias="workspaceId")
    provider: str
    voice: str
    sentences: list[WorkspaceTaskResultSentenceResponse]
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class WorkspaceTaskExportResponse(BaseModel):
    """Concatenated audio export URL for a completed workspace task."""

    model_config = ConfigDict(populate_by_name=True)

    export_url: str = Field(alias="exportUrl")
    created_at: datetime = Field(alias="createdAt")


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


def to_translation_response(view: TranslationView) -> TranslationResponse:
    """Convert an enriched translation to an API response."""

    translation = view.translation
    return TranslationResponse(
        id=translation.id,
        name=translation.name,
        novel_id=translation.novel_id,
        target_language=translation.target_language,
        configuration=to_translation_configuration_response(translation.configuration),
        status=translation.status,
        novel=to_novel_response(view.novel) if view.novel is not None else None,
        created_at=translation.created_at,
        updated_at=translation.updated_at,
        etag=translation.etag,
    )


def to_translation_detail_response(
    view: TranslationView,
) -> TranslationDetailResponse:
    base = to_translation_response(view)
    translation = view.translation
    return TranslationDetailResponse(
        **base.model_dump(),
        progress=_to_translation_progress_response(translation.progress),
        tasks=[_to_translation_task_response(task) for task in translation.tasks],
    )


def to_translation_sync_response(
    result: TranslationSyncResult,
) -> TranslationSyncResponse:
    return TranslationSyncResponse(
        translation=to_translation_detail_response(result.view),
        changes=TranslationSyncChangesResponse(
            added=result.changes.added,
            refreshed=result.changes.refreshed,
            preserved=result.changes.preserved,
            removed=result.changes.removed,
        ),
    )


def _to_translation_progress_response(
    progress: TranslationProgress,
) -> TranslationProgressResponse:
    return TranslationProgressResponse(
        total=progress.total,
        created=progress.created,
        queued=progress.queued,
        running=progress.running,
        completed=progress.completed,
        failed=progress.failed,
    )


def _to_translation_task_response(task: TranslationTask) -> TranslationTaskResponse:
    return TranslationTaskResponse(
        id=task.id,
        title=task.title,
        chapter_number=task.chapter_number,
        manifest_index=task.manifest_index,
        status=task.status,
        attempts=task.attempts,
        last_error=task.last_error,
        result_available=task.result_available,
        completed_at=task.completed_at,
        source_chapter_updated_at=task.source_chapter_updated_at,
        source_updated=task.source_updated,
        source_removed=task.source_removed,
    )


def to_translation_configuration_response(
    configuration: TranslationConfiguration | None,
) -> TranslationConfigurationResponse | None:
    if configuration is None:
        return None
    return TranslationConfigurationResponse(
        provider_id=configuration.provider_id,
        model_id=configuration.model_id,
        global_prompt=configuration.global_prompt,
    )


def to_workspace_response(view: WorkspaceView) -> WorkspaceResponse:
    """Convert an enriched workspace to its list response."""

    workspace = view.workspace
    return WorkspaceResponse(
        id=workspace.id,
        title=workspace.title,
        type=workspace.type,
        novel_id=workspace.novel_id,
        language=workspace.language,
        source_type=view.source_type,
        source_available=view.source_available,
        chapter_count=view.novel.chapter_count if view.novel else 0,
        novel=to_novel_response(view.novel) if view.novel else None,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        etag=workspace.etag,
    )


def to_workspace_detail_response(view: WorkspaceView) -> WorkspaceDetailResponse:
    """Convert an enriched workspace to its detail response."""

    return WorkspaceDetailResponse(
        **to_workspace_response(view).model_dump(),
        chapters=[to_novel_chapter_summary(chapter) for chapter in view.chapters],
        progress=_to_workspace_progress_response(view.workspace.progress),
        tasks=[_to_workspace_task_response(task) for task in view.workspace.tasks],
    )


def _to_workspace_progress_response(
    progress: WorkspaceProgress,
) -> WorkspaceProgressResponse:
    return WorkspaceProgressResponse(
        total=progress.total,
        created=progress.created,
        queued=progress.queued,
        running=progress.running,
        completed=progress.completed,
        failed=progress.failed,
    )


def _to_workspace_task_response(task: WorkspaceTask) -> WorkspaceTaskResponse:
    return WorkspaceTaskResponse(
        id=task.id,
        title=task.title,
        chapter_number=task.chapter_number,
        manifest_index=task.manifest_index,
        status=task.status,
        attempts=task.attempts,
        last_error=task.last_error,
        result_available=task.result_available,
        completed_at=task.completed_at,
        source_chapter_updated_at=task.source_chapter_updated_at,
        source_updated=task.source_updated,
        source_removed=task.source_removed,
        provider=task.provider,
        voice=task.voice,
    )


def to_workspace_task_result_response(
    result: WorkspaceResult,
) -> WorkspaceTaskResultResponse:
    """Convert a complete workspace result to its indexed API representation."""

    return WorkspaceTaskResultResponse(
        task_id=result.task_id,
        workspace_id=result.workspace_id,
        provider=result.provider,
        voice=result.voice,
        sentences=[
            WorkspaceTaskResultSentenceResponse(index=index, audio_url=audio_url)
            for index, audio_url in enumerate(result.audio_urls)
        ],
        created_at=result.created_at,
        updated_at=result.updated_at,
    )


# NovelResponse intentionally appears before the binding contract so existing
# response definitions stay grouped; resolve that forward reference explicitly.
NovelResponse.model_rebuild()
WorkspaceDetailResponse.model_rebuild()
