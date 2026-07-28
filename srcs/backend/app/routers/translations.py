"""Translation-management routes."""

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Response, status

from app.core.injection import ServiceTranslationDep
from app.core.security.authorization import SessionUser
from app.domain.requests import (
    TranslationCreateRequest,
    TranslationUpdateRequest,
    to_translation_configuration,
    to_translation_entity,
)
from app.domain.responses import (
    TranslationListResponse,
    TranslationResponse,
    to_translation_response,
)
from app.repositories.translation_repository import (
    TranslationConflictError,
    TranslationContinuationTokenError,
    TranslationNotFoundError,
)
from app.services.translation_service import TranslationNovelNotFoundError

router = APIRouter(prefix="/api/translations", tags=["translations"])


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


@router.get("/{id}", response_model=TranslationResponse, operation_id="get_translation")
def get_translation_route(
    session_user: SessionUser,
    service_translation: ServiceTranslationDep,
    id: str,
) -> TranslationResponse:
    del session_user
    view = service_translation.get_by_id(id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Translation not found")
    return to_translation_response(view)


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
    return Response(status_code=status.HTTP_204_NO_CONTENT)
