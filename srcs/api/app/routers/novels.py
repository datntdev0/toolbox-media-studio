"""Novel-management routes."""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Response, status

from app.core.dependencies import CurrentUser, NovelRepositoryDep
from app.domain.novels import Novel
from app.domain.requests import NovelCreateRequest, NovelUpdateRequest
from app.domain.responses import NovelListResponse, NovelResponse
from app.repositories.novel_repository import NovelConflictError, NovelNotFoundError
from app.services.novel_service import create_novel, delete_novel, get_novel, list_novels, update_novel

router = APIRouter(prefix="/api/novels", tags=["novels"])

IfMatchHeader = Annotated[str | None, Header(alias="If-Match")]


@router.post("", response_model=NovelResponse, status_code=status.HTTP_201_CREATED)
def create_novel_route(
    body: NovelCreateRequest,
    current_user: CurrentUser,
    novel_repository: NovelRepositoryDep,
) -> NovelResponse:
    """Create a new novel."""

    novel = create_novel(body, current_user, novel_repository)
    return to_novel_response(novel)


@router.get("", response_model=NovelListResponse)
def list_novels_route(
    current_user: CurrentUser,
    novel_repository: NovelRepositoryDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    continuation_token: Annotated[str | None, Query(alias="continuationToken")] = None,
) -> NovelListResponse:
    """List novels for the current user."""

    page = list_novels(
        current_user=current_user,
        novel_repository=novel_repository,
        limit=limit,
        continuation_token=continuation_token,
    )
    return NovelListResponse(
        items=[to_novel_response(novel) for novel in page.items],
        continuation_token=page.continuation_token,
    )


@router.get("/{id}", response_model=NovelResponse)
def get_novel_route(
    id: str,
    current_user: CurrentUser,
    novel_repository: NovelRepositoryDep,
) -> NovelResponse:
    """Fetch a novel by id."""

    try:
        novel = get_novel(id, current_user, novel_repository)
    except NovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found") from exc
    return to_novel_response(novel)


@router.patch("/{id}", response_model=NovelResponse)
def update_novel_route(
    id: str,
    body: NovelUpdateRequest,
    current_user: CurrentUser,
    novel_repository: NovelRepositoryDep,
    if_match: IfMatchHeader = None,
) -> NovelResponse:
    """Partially update a novel."""

    try:
        novel = update_novel(id, body, current_user, novel_repository, if_match)
    except NovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found") from exc
    except NovelConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Novel has changed",
        ) from exc
    return to_novel_response(novel)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_novel_route(
    id: str,
    current_user: CurrentUser,
    novel_repository: NovelRepositoryDep,
    if_match: IfMatchHeader = None,
) -> Response:
    """Soft-delete a novel."""

    try:
        delete_novel(id, current_user, novel_repository, if_match)
    except NovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found") from exc
    except NovelConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Novel has changed",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def to_novel_response(novel: Novel) -> NovelResponse:
    """Map a stored novel entity to the API response model."""

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
