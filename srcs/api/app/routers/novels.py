"""Novel-management routes."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.injection.service_provider import RepositoryNovelDep
from app.core.security.authorization import SessionUser
from app.domain.requests import NovelCreateRequest, NovelUpdateRequest, to_novel_entity
from app.domain.responses import NovelListResponse, NovelResponse, to_novel_response
from app.repositories.novel_repository import NovelConflictError

router = APIRouter(prefix="/api/novels", tags=["novels"])


@router.post("", response_model=NovelResponse, status_code=status.HTTP_201_CREATED)
def create_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    body: NovelCreateRequest,
) -> NovelResponse:
    novel_entity = to_novel_entity(body, session_user.id)
    novel_return = repository_novel.create(novel_entity)
    return to_novel_response(novel_return)


@router.get("", response_model=NovelListResponse)
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


@router.get("/{id}", response_model=NovelResponse)
def get_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    id: str,
) -> NovelResponse:
    novel_return = repository_novel.get_by_id(id=id)
    if novel_return is None or novel_return.created_by != session_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Novel not found",
        )
    return to_novel_response(novel_return)


@router.patch("/{id}", response_model=NovelResponse)
def update_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    id: str,
    body: NovelUpdateRequest,
) -> NovelResponse:
    novel_existing = repository_novel.get_by_id(id=id)
    if novel_existing is None or novel_existing.created_by != session_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Novel not found",
        )

    if "title" in body.model_fields_set and body.title is not None:
        novel_existing.title = body.title
    if "description" in body.model_fields_set:
        novel_existing.description = body.description
    if "cover_image_url" in body.model_fields_set:
        novel_existing.cover_image_url = body.cover_image_url
    if "language" in body.model_fields_set:
        novel_existing.language = body.language
    if "author" in body.model_fields_set:
        novel_existing.author = body.author
    if "tags" in body.model_fields_set:
        novel_existing.tags = list(body.tags or [])
    if "notes" in body.model_fields_set:
        novel_existing.notes = body.notes
    if "status" in body.model_fields_set and body.status is not None:
        novel_existing.status = body.status
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Novel not found",
        )

    try:
        repository_novel.delete(
            id=novel_existing.id,
            etag=None,
            deleted_by=session_user.id,
        )
    except NovelConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Novel has changed",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
