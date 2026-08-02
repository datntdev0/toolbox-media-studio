"""Translation-management routes."""

# ruff: noqa: E501

import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, Path, Query, Response, status

from app.core.exceptions import (
    BadGatewayException,
    ConflictException,
    NotFoundException,
    ServiceUnavailableException,
    StateConflictException,
    ValidationException,
)
from app.core.injection import (
    PollingQueuePublisherDep,
    ProviderTranslationServiceFactoryDep,
    RealtimeHubDep,
    RepositoryNovelChapterDep,
    RepositoryNovelDep,
    RepositoryTranslationDep,
    RepositoryTranslationResultDep,
)
from app.core.security.authorization import SessionUser
from app.domain.novels import Novel, NovelChapter
from app.domain.requests import (
    TranslationCreateRequest,
    TranslationPreviewRequest,
    TranslationPreviewResponse,
    TranslationStartRequest,
    TranslationUpdateRequest,
    to_translation_configuration,
    to_translation_entity,
)
from app.domain.responses import (
    TranslationDetailResponse,
    TranslationListResponse,
    TranslationResponse,
    to_translation_detail_response,
    to_translation_response,
)
from app.domain.translation_results import (
    TranslationResult,
    TranslationResultResponse,
    TranslationResultUpdateRequest,
    to_translation_result_response,
)
from app.domain.translations import (
    Translation,
    TranslationStatus,
    TranslationTask,
    TranslationTaskStatus,
    TranslationView,
)
from app.events.translation_handler import (
    TRANSLATION_QUEUE_NAME,
    build_translation_event,
    build_translation_updated_payload,
)
from app.providers.translation_service_provider import (
    TranslationServiceProviderError,
    UnsupportedTranslationServiceProviderError,
)
from app.repositories.novel_repository import NovelNotFoundError, NovelRepository
from app.repositories.translation_repository import (
    TranslationChapterRangeError,
    TranslationConflictError,
    TranslationContinuationTokenError,
    TranslationNotFoundError,
)
from app.repositories.translation_result_repository import TranslationResultTooLargeError

router = APIRouter(prefix="/api/translations", tags=["translations"])


@router.post("/preview", response_model=TranslationPreviewResponse, operation_id="preview_translation")
def preview_translation_route(
    session_user: SessionUser,
    repository_novel_chapter: RepositoryNovelChapterDep,
    translation_service_provider_factory: ProviderTranslationServiceFactoryDep,
    body: TranslationPreviewRequest,
) -> TranslationPreviewResponse:
    """Translate one chapter without creating or updating a translation project."""

    del session_user
    chapter = repository_novel_chapter.get_by_id(body.chapter)
    if chapter is None:
        raise NotFoundException("Novel chapter not found")
    if chapter.source_removed or not chapter.content_available:
        raise StateConflictException("Novel chapter content is unavailable")
    try:
        provider = translation_service_provider_factory.get(body.provider)
        translated = provider.translate(
            model=body.model,
            language=body.language,
            instruction=body.instruction,
            chapter_title=chapter.title,
            chapter_content=chapter.content,
        )
    except UnsupportedTranslationServiceProviderError as exc:
        raise ValidationException(str(exc)) from exc
    except TranslationServiceProviderError as exc:
        raise BadGatewayException(str(exc)) from exc
    return TranslationPreviewResponse(title=translated.title, content=translated.content)


@router.post("", response_model=TranslationResponse, status_code=status.HTTP_201_CREATED, operation_id="create_translation")
def create_translation_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    repository_translation: RepositoryTranslationDep,
    body: Annotated[TranslationCreateRequest, Body(...)],
) -> TranslationResponse:
    novel = _require_novel(repository_novel, body.novel_id)
    translation = to_translation_entity(body, session_user.id)
    translation.tasks = []
    created = repository_translation.create(translation)
    return to_translation_response(TranslationView(translation=created, novel=novel))


@router.get("", response_model=TranslationListResponse, operation_id="list_translations")
def list_translations_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    repository_translation: RepositoryTranslationDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    continuation_token: Annotated[str | None, Query(alias="continuationToken")] = None,
) -> TranslationListResponse:
    del session_user
    try:
        page = repository_translation.list(limit, continuation_token)
    except TranslationContinuationTokenError as exc:
        raise ValidationException(str(exc)) from exc
    return TranslationListResponse(
        items=[
            to_translation_response(_translation_view(item, repository_novel))
            for item in page.items
        ],
        continuationToken=page.continuation_token,
    )


@router.get("/{id}", response_model=TranslationDetailResponse, operation_id="get_translation")
def get_translation_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    repository_translation: RepositoryTranslationDep,
    id: str,
) -> TranslationDetailResponse:
    del session_user
    translation = repository_translation.get_by_id(id)
    if translation is None:
        raise NotFoundException("Translation not found")
    return to_translation_detail_response(_translation_view(translation, repository_novel))


@router.patch("/{id}/start", response_model=TranslationDetailResponse, status_code=status.HTTP_202_ACCEPTED, operation_id="start_translation")
def start_translation_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    repository_novel_chapter: RepositoryNovelChapterDep,
    repository_translation: RepositoryTranslationDep,
    queue_publisher: PollingQueuePublisherDep,
    realtime_hub: RealtimeHubDep,
    id: str,
    body: TranslationStartRequest,
) -> TranslationDetailResponse:
    del session_user
    translation = repository_translation.get_by_id(id)
    if translation is None:
        raise NotFoundException("Translation not found")
    if translation.configuration is None:
        raise StateConflictException("Translation is not configured")

    chapter_snapshots = [
        _task_from_chapter(chapter)
        for chapter in repository_novel_chapter.list(translation.novel_id).items
        if not chapter.source_removed
        and body.chapter_index_from <= chapter.manifest_index + 1 <= body.chapter_index_to
    ]
    if not chapter_snapshots:
        raise ValidationException("No novel chapters match the requested chapter index range")

    for _ in range(3):
        try:
            queued = repository_translation.queue_tasks(
                translation.id,
                tasks=chapter_snapshots,
                force=body.force,
                etag=translation.etag,
            )
            break
        except TranslationConflictError:
            latest = repository_translation.get_by_id(translation.id)
            if latest is None:
                raise NotFoundException("Translation not found") from None
            translation = latest
        except TranslationChapterRangeError as exc:
            raise ValidationException(str(exc)) from exc
    else:
        raise StateConflictException("Translation changed while tasks were being queued")

    translation = queued.translation
    if queued.tasks:
        realtime_hub.publish(
            "translation.updated",
            build_translation_updated_payload(translation),
        )
    try:
        for task in queued.tasks:
            queue_publisher.publish(
                TRANSLATION_QUEUE_NAME,
                build_translation_event(
                    translation,
                    task,
                    refetch=body.refetch,
                ),
            )
    except Exception as exc:
        raise ServiceUnavailableException(
            "Some translation tasks could not be queued; retry with force"
        ) from exc
    return to_translation_detail_response(_translation_view(translation, repository_novel))


@router.patch("/{id}/stop", response_model=TranslationDetailResponse, operation_id="stop_translation")
def stop_translation_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    repository_translation: RepositoryTranslationDep,
    realtime_hub: RealtimeHubDep,
    id: str,
) -> TranslationDetailResponse:
    del session_user
    translation = repository_translation.get_by_id(id)
    if translation is None:
        raise NotFoundException("Translation not found")
    for _ in range(3):
        try:
            updated = repository_translation.stop_queued_tasks(
                translation.id,
                etag=translation.etag,
            )
            break
        except TranslationConflictError:
            latest = repository_translation.get_by_id(translation.id)
            if latest is None:
                raise NotFoundException("Translation not found") from None
            translation = latest
    else:
        raise StateConflictException("Translation changed while queued tasks were being stopped")
    realtime_hub.publish(
        "translation.updated",
        build_translation_updated_payload(updated),
    )
    return to_translation_detail_response(_translation_view(updated, repository_novel))


@router.get("/{id}/result/{taskId}", response_model=TranslationResultResponse, operation_id="get_translation_result")
def get_translation_result_route(
    session_user: SessionUser,
    repository_translation: RepositoryTranslationDep,
    repository_translation_result: RepositoryTranslationResultDep,
    id: str,
    task_id: Annotated[str, Path(alias="taskId")],
) -> TranslationResultResponse:
    del session_user
    translation = repository_translation.get_by_id(id)
    if translation is None:
        raise NotFoundException("Translation not found")
    task = next((item for item in translation.tasks if item.id == task_id), None)
    if task is None:
        raise NotFoundException("Translation task not found")
    if not task.result_available:
        raise StateConflictException("Translation result is not available")
    try:
        result = repository_translation_result.get(translation.id, task.id)
    except Exception as exc:
        raise ServiceUnavailableException("Translation result is unavailable") from exc
    if result is None:
        raise ServiceUnavailableException("Translation result is unavailable")
    return to_translation_result_response(result)


@router.put("/{id}/result/{taskId}", response_model=TranslationResultResponse, operation_id="update_translation_result")
def update_translation_result_route(
    session_user: SessionUser,
    repository_translation: RepositoryTranslationDep,
    repository_translation_result: RepositoryTranslationResultDep,
    id: str,
    task_id: Annotated[str, Path(alias="taskId")],
    body: Annotated[TranslationResultUpdateRequest, Body(...)],
) -> TranslationResultResponse:
    """Create or replace the manually edited result for one translation task."""

    del session_user
    translation = repository_translation.get_by_id(id)
    if translation is None:
        raise NotFoundException("Translation not found")
    task = next((item for item in translation.tasks if item.id == task_id), None)
    if task is None:
        raise NotFoundException("Translation task not found")
    if task.source_removed:
        raise StateConflictException("Source chapter is unavailable")
    if task.status in {TranslationTaskStatus.QUEUED, TranslationTaskStatus.RUNNING}:
        raise StateConflictException("Translation task is currently processing")

    paragraphs = _split_translation_content(body.content)
    now = datetime.now(UTC)
    try:
        existing = repository_translation_result.get(translation.id, task.id)
        result = repository_translation_result.upsert(
            TranslationResult(
                id=task.id,
                translation_id=translation.id,
                task_id=task.id,
                title=(
                    body.title.strip()
                    if body.title.strip()
                    else existing.title if existing is not None else task.title
                ),
                chapter_number=(
                    existing.chapter_number if existing is not None else task.chapter_number
                ),
                content=paragraphs,
                created_at=existing.created_at if existing is not None else now,
                updated_at=now,
            )
        )
    except TranslationResultTooLargeError as exc:
        raise ValidationException(str(exc)) from exc
    except Exception as exc:
        raise ServiceUnavailableException("Translation result could not be saved") from exc

    for _ in range(3):
        try:
            repository_translation.update_task(
                translation.id,
                task.id,
                TranslationTaskStatus.COMPLETED,
                attempts=task.attempts,
                error=None,
                result_available=True,
                completed_at=now,
                source_chapter_updated_at=None,
                clear_source_updated=True,
                etag=translation.etag,
            )
            break
        except TranslationConflictError:
            latest = repository_translation.get_by_id(translation.id)
            if latest is None:
                raise NotFoundException("Translation not found") from None
            translation = latest
            task = next((item for item in translation.tasks if item.id == task_id), None)
            if task is None:
                raise NotFoundException("Translation task not found") from None
            if task.source_removed:
                raise StateConflictException("Source chapter is unavailable") from None
            if task.status in {TranslationTaskStatus.QUEUED, TranslationTaskStatus.RUNNING}:
                raise StateConflictException("Translation task is currently processing") from None
    else:
        raise StateConflictException("Translation changed while the result was being saved")

    return to_translation_result_response(result)


def _split_translation_content(content: str) -> list[str]:
    normalized = content.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    return [
        paragraph.strip()
        for paragraph in re.split(r"\n[ \t]*\n+", normalized)
        if paragraph.strip()
    ]


@router.put("/{id}", response_model=TranslationResponse, operation_id="update_translation")
def update_translation_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    repository_translation: RepositoryTranslationDep,
    id: str,
    body: Annotated[TranslationUpdateRequest, Body(...)],
) -> TranslationResponse:
    translation = repository_translation.get_by_id(id)
    if translation is None:
        raise NotFoundException("Translation not found")
    novel = _require_novel(repository_novel, body.novel_id)
    if body.novel_id != translation.novel_id and translation.tasks:
        raise StateConflictException(
            "Translation novel cannot change after tasks have been created"
        )

    translation.name = body.name.strip()
    translation.novel_id = body.novel_id
    translation.target_language = body.target_language.strip()
    translation.configuration = to_translation_configuration(body.configuration)
    translation.updated_at = datetime.now(UTC)
    translation.updated_by = session_user.id
    if (
        translation.status == TranslationStatus.NEEDS_SETUP
        and translation.configuration is not None
    ):
        translation.status = TranslationStatus.READY
    elif (
        translation.status == TranslationStatus.READY
        and translation.configuration is None
    ):
        translation.status = TranslationStatus.NEEDS_SETUP
    try:
        updated = repository_translation.update(translation, body.etag)
    except TranslationConflictError as exc:
        raise ConflictException(str(exc)) from exc
    except TranslationNotFoundError as exc:
        raise NotFoundException("Translation not found") from exc
    return to_translation_response(TranslationView(translation=updated, novel=novel))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, operation_id="delete_translation")
def delete_translation_route(
    session_user: SessionUser,
    repository_translation: RepositoryTranslationDep,
    repository_translation_result: RepositoryTranslationResultDep,
    id: str,
) -> Response:
    translation = repository_translation.get_by_id(id)
    if translation is None:
        raise NotFoundException("Translation not found")
    try:
        repository_translation_result.delete_by_translation(id)
    except Exception as exc:
        raise ServiceUnavailableException("Translation results could not be deleted") from exc
    try:
        repository_translation.delete(id, etag=None, deleted_by=session_user.id)
    except TranslationNotFoundError as exc:
        raise NotFoundException("Translation not found") from exc
    except TranslationConflictError as exc:
        raise ConflictException(str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _task_from_chapter(chapter: NovelChapter) -> TranslationTask:
    return TranslationTask(
        id=chapter.id,
        title=chapter.title,
        chapter_number=chapter.chapter_number,
        manifest_index=chapter.manifest_index,
        source_chapter_updated_at=chapter.updated_at,
    )


def _translation_view(
    translation: Translation,
    repository_novel: NovelRepository,
) -> TranslationView:
    try:
        novel = repository_novel.get_by_id(translation.novel_id)
    except NovelNotFoundError:
        novel = None
    return TranslationView(translation=translation, novel=novel)


def _require_novel(repository_novel: NovelRepository, novel_id: str) -> Novel:
    try:
        return repository_novel.get_by_id(novel_id)
    except NovelNotFoundError as exc:
        raise NotFoundException("Novel not found") from exc
