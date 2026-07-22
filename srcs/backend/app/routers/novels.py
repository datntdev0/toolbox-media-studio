"""Novel-management routes."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status

from app.core.injection import ProviderPublicBlobDep, RepositoryNovelDep
from app.core.security.authorization import SessionUser
from app.domain.novels import NovelStatus
from app.domain.requests import NovelCreateRequest, to_novel_entity
from app.domain.responses import NovelListResponse, NovelResponse, to_novel_response
from app.providers.blob_storage_provider import BlobStorageError, validate_cover_content
from app.repositories.novel_repository import NovelConflictError

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
    provider_public_blob: ProviderPublicBlobDep,
    title: Annotated[str, Form(min_length=1)],
    description: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form()] = None,
    author: Annotated[str | None, Form()] = None,
    tags: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
    cover_image: Annotated[UploadFile | None, File(alias="coverImage")] = None,
) -> NovelResponse:
    body = NovelCreateRequest(
        title=title,
        description=_nullable_text(description),
        language=_nullable_text(language),
        author=_nullable_text(author),
        tags=_parse_tags(tags),
        notes=_nullable_text(notes),
    )
    novel_entity = to_novel_entity(body, session_user.id)
    if cover_image is not None:
        novel_entity.cover_image_url = _upload_cover(
            provider_public_blob, novel_entity.id, cover_image
        )
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


@router.get("/{id}", response_model=NovelResponse, operation_id="get_novel")
def get_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    id: str,
) -> NovelResponse:
    novel_return = repository_novel.get_by_id(id=id)
    if novel_return is None or novel_return.created_by != session_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found")
    return to_novel_response(novel_return)


@router.put("/{id}", response_model=NovelResponse, operation_id="update_novel")
def update_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    provider_public_blob: ProviderPublicBlobDep,
    id: str,
    title: Annotated[str | None, Form(min_length=1)] = None,
    description: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form()] = None,
    author: Annotated[str | None, Form()] = None,
    tags: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
    status_value: Annotated[NovelStatus | None, Form(alias="status")] = None,
    etag: Annotated[str | None, Form()] = None,
    cover_image: Annotated[UploadFile | None, File(alias="coverImage")] = None,
    clear_cover_image: Annotated[bool, Form()] = False,
) -> NovelResponse:
    novel_existing = repository_novel.get_by_id(id=id)
    if novel_existing is None or novel_existing.created_by != session_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found")

    supplied = {
        "title": title,
        "description": description,
        "language": language,
        "author": author,
        "tags": tags,
        "notes": notes,
        "status": status_value,
    }
    if title is not None:
        novel_existing.title = title
    if description is not None:
        novel_existing.description = _nullable_text(description)
    if language is not None:
        novel_existing.language = _nullable_text(language)
    if author is not None:
        novel_existing.author = _nullable_text(author)
    if tags is not None:
        novel_existing.tags = _parse_tags(tags)
    if notes is not None:
        novel_existing.notes = _nullable_text(notes)
    if status_value is not None:
        novel_existing.status = status_value
    if cover_image is not None:
        novel_existing.cover_image_url = _upload_cover(
            provider_public_blob, novel_existing.id, cover_image
        )
    elif clear_cover_image:
        novel_existing.cover_image_url = None

    if (
        not any(value is not None for value in supplied.values())
        and cover_image is None
        and not clear_cover_image
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one property is required",
        )

    novel_existing.updated_at = datetime.now(UTC)
    novel_existing.updated_by = session_user.id
    try:
        novel_return = repository_novel.update(novel_existing, etag)
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


def _upload_cover(provider: ProviderPublicBlobDep, novel_id: str, cover_image: UploadFile) -> str:
    try:
        content = cover_image.file.read(1024 * 1024 + 1)
        content_type = validate_cover_content(content, cover_image.content_type or "")
        return provider.upload_cover(novel_id, content, content_type)
    except BlobStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


def _nullable_text(value: str | None) -> str | None:
    if value is None or value == "__null__":
        return None
    return value.strip() or None


def _parse_tags(value: str | None) -> list[str]:
    if not value:
        return []
    return [tag.strip() for tag in value.split(",") if tag.strip()]
