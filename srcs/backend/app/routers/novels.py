"""Novel-management routes."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Path, Query, Response, status

from app.core.injection import RepositoryNovelDep, ServiceNovelBindingDep
from app.core.security.authorization import SessionUser
from app.domain.novels import NovelBindRequest, NovelChapterUpdateRequest
from app.domain.requests import NovelCreateRequest, NovelUpdateRequest, to_novel_entity
from app.domain.responses import (
    NovelChapterContentResponse,
    NovelDetailResponse,
    NovelListResponse,
    NovelResponse,
    NovelSyncResponse,
    to_novel_chapter_summary,
    to_novel_detail_response,
    to_novel_response,
    to_novel_sync_response,
)
from app.repositories.novel_repository import NovelConflictError
from app.services.novel_binding_service import (
    NovelBindingConcurrencyError,
    NovelBindingConflictError,
    NovelBindingNotFoundError,
)

router = APIRouter(prefix="/api/novels", tags=["novels"])


@router.post(
    "",
    response_model=NovelResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_novel",
)
def create_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    body: Annotated[NovelCreateRequest, Body(...)],
) -> NovelResponse:
    novel_entity = to_novel_entity(body, session_user.id)
    novel_return = repository_novel.create(novel_entity)
    return to_novel_response(novel_return)


@router.get("", response_model=NovelListResponse, operation_id="list_novels")
def list_novels_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    continuation_token: Annotated[str | None, Query(alias="continuationToken")] = None,
) -> NovelListResponse:
    page = repository_novel.list(limit=limit, continuation_token=continuation_token)
    return NovelListResponse(
        items=[
            to_novel_response(novel)
            for novel in page.items
            if novel.created_by == session_user.id
        ],
        continuation_token=page.continuation_token,
    )


@router.get("/{id}", response_model=NovelDetailResponse, operation_id="get_novel")
def get_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    binding_service: ServiceNovelBindingDep,
    id: str,
) -> NovelDetailResponse:
    novel_return = repository_novel.get_by_id(id=id)
    if novel_return is None or novel_return.created_by != session_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found")
    try:
        novel_return, chapters = binding_service.get_detail(id)
    except NovelBindingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_novel_detail_response(novel_return, chapters)


@router.patch(
    "/{id}/bind",
    response_model=NovelSyncResponse,
    operation_id="bind_novel",
)
def bind_novel_route(
    session_user: SessionUser,
    binding_service: ServiceNovelBindingDep,
    id: str,
    body: Annotated[NovelBindRequest, Body(...)],
) -> NovelSyncResponse:
    """Bind any scraping to an empty novel and clone its current chapters."""

    try:
        result = binding_service.bind(
            id,
            body.scraping_id,
            updated_by=session_user.id,
        )
    except NovelBindingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NovelBindingConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except NovelBindingConcurrencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc
    return to_novel_sync_response(result)


@router.patch(
    "/{id}/sync",
    response_model=NovelSyncResponse,
    operation_id="sync_novel",
)
def sync_novel_route(
    session_user: SessionUser,
    binding_service: ServiceNovelBindingDep,
    id: str,
) -> NovelSyncResponse:
    """Merge the latest bound scraping manifest and available content."""

    try:
        result = binding_service.sync(id, updated_by=session_user.id)
    except NovelBindingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NovelBindingConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except NovelBindingConcurrencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc
    return to_novel_sync_response(result)


@router.get(
    "/{id}/chapters/{chapterId}",
    response_model=NovelChapterContentResponse,
    operation_id="get_novel_chapter",
)
def get_novel_chapter_route(
    session_user: SessionUser,
    binding_service: ServiceNovelBindingDep,
    id: str,
    chapter_id: Annotated[str, Path(alias="chapterId")],
) -> NovelChapterContentResponse:
    """Return a cloned chapter without applying an ownership constraint."""

    del session_user
    try:
        chapter, content = binding_service.get_chapter_content(id, chapter_id)
    except NovelBindingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return NovelChapterContentResponse(
        **to_novel_chapter_summary(chapter).model_dump(),
        content=content,
    )


@router.patch(
    "/{id}/chapters/{chapterId}",
    response_model=NovelChapterContentResponse,
    operation_id="update_novel_chapter",
)
def update_novel_chapter_route(
    session_user: SessionUser,
    binding_service: ServiceNovelBindingDep,
    id: str,
    chapter_id: Annotated[str, Path(alias="chapterId")],
    body: Annotated[NovelChapterUpdateRequest, Body(...)],
) -> NovelChapterContentResponse:
    """Replace cloned content without applying an ownership constraint."""

    try:
        chapter, content = binding_service.update_chapter_content(
            id,
            chapter_id,
            body.content,
            etag=body.etag,
            updated_by=session_user.id,
        )
    except NovelBindingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NovelBindingConcurrencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc
    return NovelChapterContentResponse(
        **to_novel_chapter_summary(chapter).model_dump(),
        content=content,
    )


@router.put("/{id}", response_model=NovelResponse, operation_id="update_novel")
def update_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    id: str,
    body: Annotated[NovelUpdateRequest, Body(...)],
) -> NovelResponse:
    novel_existing = repository_novel.get_by_id(id=id)
    if novel_existing is None or novel_existing.created_by != session_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found")

    supplied = body.model_fields_set - {"etag"}
    if not supplied:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one property is required",
        )

    for field in supplied:
        value = getattr(body, field)
        if field == "tags":
            value = list(value or [])
        setattr(novel_existing, field, value)

    novel_existing.updated_at = datetime.now(UTC)
    novel_existing.updated_by = session_user.id
    try:
        novel_return = repository_novel.update(novel_existing, body.etag)
    except NovelConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Novel has changed",
        ) from exc
    return to_novel_response(novel_return)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    id: str,
) -> Response:
    novel_existing = repository_novel.get_by_id(id=id)
    if novel_existing is None or novel_existing.created_by != session_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found")
    try:
        repository_novel.delete(id=novel_existing.id, etag=None, deleted_by=session_user.id)
    except NovelConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Novel has changed",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
