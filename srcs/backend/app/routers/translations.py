"""Translation-management routes."""

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Path, Query, Response, status

from app.core.injection import (
    PollingQueuePublisherDep,
    RealtimeHubDep,
    RepositoryNovelChapterDep,
    RepositoryTranslationDep,
    RepositoryTranslationResultDep,
    ServiceTranslationDep,
    config,
)
from app.core.security.authorization import SessionUser
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
    TranslationSyncResponse,
    to_translation_detail_response,
    to_translation_response,
    to_translation_sync_response,
)
from app.domain.translation_results import (
    TranslationResultResponse,
    to_translation_result_response,
)
from app.domain.translations import TranslationView
from app.events.translation_handler import (
    TRANSLATION_QUEUE_NAME,
    build_translation_event,
    build_translation_updated_payload,
)
from app.providers.translation_provider import (
    TranslationProviderError,
    UnsupportedTranslationProviderError,
    translate_preview,
)
from app.repositories.translation_repository import (
    TranslationChapterRangeError,
    TranslationConflictError,
    TranslationContinuationTokenError,
    TranslationNotFoundError,
)
from app.services.translation_service import (
    TranslationNovelNotFoundError,
    TranslationResultDeleteError,
    TranslationSyncConflictError,
)

router = APIRouter(prefix="/api/translations", tags=["translations"])


@router.post(
    "/preview",
    response_model=TranslationPreviewResponse,
    operation_id="preview_translation",
)
def preview_translation_route(
    session_user: SessionUser,
    repository_novel_chapter: RepositoryNovelChapterDep,
    body: TranslationPreviewRequest,
) -> TranslationPreviewResponse:
    """Translate one chapter without creating or updating a translation project."""

    del session_user
    chapter = repository_novel_chapter.get_by_id(body.chapter)
    if chapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Novel chapter not found",
        )
    if chapter.source_removed or not chapter.content_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Novel chapter content is unavailable",
        )
    try:
        translated = translate_preview(
            provider=body.provider,
            model=body.model,
            language=body.language,
            instruction=body.instruction,
            chapter_title=chapter.title,
            chapter_content=chapter.content,
            config=config,
        )
    except UnsupportedTranslationProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except TranslationProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return TranslationPreviewResponse(title=translated.title, content=translated.content)


@router.post(
    "",
    response_model=TranslationResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_translation",
)
def create_translation_route(
    session_user: SessionUser,
    service_translation: ServiceTranslationDep,
    body: Annotated[TranslationCreateRequest, Body(...)],
) -> TranslationResponse:
    try:
        view = service_translation.create(to_translation_entity(body, session_user.id))
    except TranslationNovelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Novel not found",
        ) from exc
    return to_translation_response(view)


@router.get("", response_model=TranslationListResponse, operation_id="list_translations")
def list_translations_route(
    session_user: SessionUser,
    service_translation: ServiceTranslationDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    continuation_token: Annotated[str | None, Query(alias="continuationToken")] = None,
) -> TranslationListResponse:
    del session_user
    try:
        page = service_translation.list(limit, continuation_token)
    except TranslationContinuationTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return TranslationListResponse(
        items=[to_translation_response(item) for item in page.items],
        continuationToken=page.continuation_token,
    )


@router.get(
    "/{id}",
    response_model=TranslationDetailResponse,
    operation_id="get_translation",
)
def get_translation_route(
    session_user: SessionUser,
    service_translation: ServiceTranslationDep,
    id: str,
) -> TranslationDetailResponse:
    del session_user
    view = service_translation.get_by_id(id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Translation not found")
    return to_translation_detail_response(view)


@router.patch(
    "/{id}/sync",
    response_model=TranslationSyncResponse,
    operation_id="sync_translation",
)
def sync_translation_route(
    session_user: SessionUser,
    service_translation: ServiceTranslationDep,
    realtime_hub: RealtimeHubDep,
    id: str,
) -> TranslationSyncResponse:
    try:
        result = service_translation.sync(id, updated_by=session_user.id)
    except (TranslationNotFoundError, TranslationNovelNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation or connected novel not found",
        ) from exc
    except TranslationSyncConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc
    realtime_hub.publish(
        "translation.updated",
        build_translation_updated_payload(result.view.translation),
    )
    return to_translation_sync_response(result)


@router.patch(
    "/{id}/start",
    response_model=TranslationDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="start_translation",
)
def start_translation_route(
    session_user: SessionUser,
    repository_translation: RepositoryTranslationDep,
    service_translation: ServiceTranslationDep,
    queue_publisher: PollingQueuePublisherDep,
    realtime_hub: RealtimeHubDep,
    id: str,
    body: TranslationStartRequest,
) -> TranslationDetailResponse:
    del session_user
    translation = repository_translation.get_by_id(id)
    if translation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Translation not found")
    if translation.configuration is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Translation is not configured",
        )

    for _ in range(3):
        try:
            queued = repository_translation.queue_tasks(
                translation.id,
                chapter_index_from=body.chapter_index_from,
                chapter_index_to=body.chapter_index_to,
                force=body.force,
                etag=translation.etag,
            )
            break
        except TranslationConflictError:
            latest = repository_translation.get_by_id(translation.id)
            if latest is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Translation not found",
                ) from None
            translation = latest
        except TranslationChapterRangeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Translation changed while tasks were being queued",
        )

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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Some translation tasks could not be queued; retry with force",
        ) from exc
    view = service_translation.get_by_id(translation.id)
    return to_translation_detail_response(
        view or TranslationView(translation=translation, novel=None)
    )


@router.patch(
    "/{id}/stop",
    response_model=TranslationDetailResponse,
    operation_id="stop_translation",
)
def stop_translation_route(
    session_user: SessionUser,
    repository_translation: RepositoryTranslationDep,
    service_translation: ServiceTranslationDep,
    realtime_hub: RealtimeHubDep,
    id: str,
) -> TranslationDetailResponse:
    del session_user
    translation = repository_translation.get_by_id(id)
    if translation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Translation not found")
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
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Translation not found",
                ) from None
            translation = latest
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Translation changed while queued tasks were being stopped",
        )
    realtime_hub.publish(
        "translation.updated",
        build_translation_updated_payload(updated),
    )
    view = service_translation.get_by_id(updated.id)
    return to_translation_detail_response(
        view or TranslationView(translation=updated, novel=None)
    )


@router.get(
    "/{id}/result/{taskId}",
    response_model=TranslationResultResponse,
    operation_id="get_translation_result",
)
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Translation not found")
    task = next((item for item in translation.tasks if item.id == task_id), None)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation task not found",
        )
    if not task.result_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Translation result is not available",
        )
    try:
        result = repository_translation_result.get(translation.id, task.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Translation result is unavailable",
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Translation result is unavailable",
        )
    return to_translation_result_response(result)


@router.put("/{id}", response_model=TranslationResponse, operation_id="update_translation")
def update_translation_route(
    session_user: SessionUser,
    service_translation: ServiceTranslationDep,
    id: str,
    body: Annotated[TranslationUpdateRequest, Body(...)],
) -> TranslationResponse:
    try:
        view = service_translation.update(
            id,
            name=body.name,
            novel_id=body.novel_id,
            target_language=body.target_language,
            configuration=to_translation_configuration(body.configuration),
            etag=body.etag,
            updated_by=session_user.id,
        )
    except TranslationNovelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Novel not found",
        ) from exc
    except TranslationSyncConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except TranslationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc
    except TranslationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation not found",
        ) from exc
    return to_translation_response(view)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_translation",
)
def delete_translation_route(
    session_user: SessionUser,
    service_translation: ServiceTranslationDep,
    id: str,
) -> Response:
    try:
        service_translation.delete(id, session_user.id)
    except TranslationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation not found",
        ) from exc
    except TranslationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc
    except TranslationResultDeleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Translation results could not be deleted",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
