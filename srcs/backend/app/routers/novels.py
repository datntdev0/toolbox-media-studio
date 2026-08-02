"""Novel-management routes."""

# ruff: noqa: E501

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, File, Path, Query, Response, UploadFile, status

from app.core.exceptions import NotFoundException, StateConflictException, ValidationException
from app.core.injection import (
    ProviderPublicBlobDep,
    RepositoryNovelDep,
    ServiceNovelBindingDep,
    ServiceNovelLanguageDep,
)
from app.core.security.authorization import SessionUser
from app.domain.novels import NovelBindRequest, NovelChapterUpdateRequest
from app.domain.requests import NovelCreateRequest, NovelUpdateRequest, to_novel_entity
from app.domain.responses import (
    NovelChapterContentResponse,
    NovelDetailResponse,
    NovelLanguageListResponse,
    NovelLanguageResponse,
    NovelListResponse,
    NovelResponse,
    NovelSyncResponse,
    to_novel_chapter_summary,
    to_novel_detail_response,
    to_novel_response,
    to_novel_sync_response,
)
from app.providers.blob_storage_provider import BlobStorageError, validate_cover_content
from app.services.novel_binding_service import NovelBindingConflictError

router = APIRouter(prefix="/api/novels", tags=["novels"])


@router.post("", response_model=NovelResponse, status_code=status.HTTP_201_CREATED, operation_id="create_novel")
def create_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    body: Annotated[NovelCreateRequest, Body(...)],
) -> NovelResponse:
    novel_entity = to_novel_entity(body, session_user.id)
    novel_return = repository_novel.create(novel_entity)
    return to_novel_response(novel_return)


@router.get("", response_model=NovelListResponse, status_code=status.HTTP_200_OK, operation_id="list_novels")
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


@router.get("/{id}", response_model=NovelDetailResponse, status_code=status.HTTP_200_OK, operation_id="get_novel")
def get_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    binding_service: ServiceNovelBindingDep,
    id: str,
) -> NovelDetailResponse:
    novel_return = repository_novel.get_by_id(id=id)
    novel_return, chapters = binding_service.get_detail(id)
    return to_novel_detail_response(novel_return, chapters)


@router.patch("/{id}/bind", response_model=NovelSyncResponse, status_code=status.HTTP_200_OK, operation_id="bind_novel")
def bind_novel_route(
    session_user: SessionUser,
    binding_service: ServiceNovelBindingDep,
    id: str,
    body: Annotated[NovelBindRequest, Body(...)],
) -> NovelSyncResponse:
    """Bind any scraping to an empty novel and clone its current chapters."""

    try:
        result = binding_service.bind(id, body.scraping_id, updated_by=session_user.id)
    except NovelBindingConflictError as exc:
        raise StateConflictException(str(exc)) from exc
    return to_novel_sync_response(result)


@router.patch("/{id}/sync", response_model=NovelSyncResponse, status_code=status.HTTP_200_OK, operation_id="sync_novel")
def sync_novel_route(
    session_user: SessionUser,
    binding_service: ServiceNovelBindingDep,
    id: str,
) -> NovelSyncResponse:
    """Merge the latest bound scraping manifest and available content."""

    try:
        result = binding_service.sync(id, updated_by=session_user.id)
    except NovelBindingConflictError as exc:
        raise StateConflictException(str(exc)) from exc
    return to_novel_sync_response(result)


@router.get("/{id}/languages", response_model=NovelLanguageListResponse, status_code=status.HTTP_200_OK, operation_id="list_novel_languages")
def list_novel_languages_route(
    session_user: SessionUser,
    service_novel_language: ServiceNovelLanguageDep,
    id: str,
) -> NovelLanguageListResponse:
    """Return the original and unique translated languages for a novel."""

    del session_user
    languages = service_novel_language.list_languages(id)
    return NovelLanguageListResponse(
        items=[
            NovelLanguageResponse(code=item.code, source_type=item.source_type)
            for item in languages
        ]
    )


@router.get("/{id}/chapters/{chapterId}", response_model=NovelChapterContentResponse, status_code=status.HTTP_200_OK, operation_id="get_novel_chapter")
def get_novel_chapter_route(
    session_user: SessionUser,
    service_novel_language: ServiceNovelLanguageDep,
    id: str,
    chapter_id: Annotated[str, Path(alias="chapterId")],
    language: Annotated[str | None, Query()] = None,
) -> NovelChapterContentResponse:
    """Return original or translated chapter content without ownership filtering."""

    del session_user
    chapter, content = service_novel_language.get_chapter_content(
        id,
        chapter_id,
        language,
    )
    return NovelChapterContentResponse(
        **to_novel_chapter_summary(chapter).model_dump(),
        content=content,
    )


@router.put("/{id}/chapters/{chapterId}", response_model=NovelChapterContentResponse, status_code=status.HTTP_200_OK, operation_id="update_novel_chapter")
def update_novel_chapter_route(
    session_user: SessionUser,
    binding_service: ServiceNovelBindingDep,
    id: str,
    chapter_id: Annotated[str, Path(alias="chapterId")],
    body: Annotated[NovelChapterUpdateRequest, Body(...)],
) -> NovelChapterContentResponse:
    """Replace cloned content without applying an ownership constraint."""

    chapter, content = binding_service.update_chapter_content(
        id,
        chapter_id,
        body.content,
        etag=body.etag,
        updated_by=session_user.id,
    )
    return NovelChapterContentResponse(
        **to_novel_chapter_summary(chapter).model_dump(),
        content=content,
    )


@router.put("/{id}/cover", response_model=NovelResponse, status_code=status.HTTP_200_OK, operation_id="upload_novel_cover")
def upload_novel_cover_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    provider_public_blob: ProviderPublicBlobDep,
    id: str,
    cover_image: Annotated[UploadFile, File(alias="coverImage")],
) -> NovelResponse:
    """Upload and attach a JPEG or PNG cover image to a novel."""

    novel = repository_novel.get_by_id(id=id)
    if novel.created_by != session_user.id:
        raise NotFoundException("Novel not found")
    try:
        content = cover_image.file.read(1024 * 1024 + 1)
        content_type = validate_cover_content(content, cover_image.content_type or "")
        novel.cover_image_url = provider_public_blob.upload_cover(id, content, content_type)
    except BlobStorageError as exc:
        raise ValidationException(str(exc)) from exc
    novel.updated_at = datetime.now(UTC)
    novel.updated_by = session_user.id
    return to_novel_response(repository_novel.update(novel, novel.etag))


@router.put("/{id}", response_model=NovelResponse, status_code=status.HTTP_200_OK, operation_id="update_novel")
def update_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    id: str,
    body: Annotated[NovelUpdateRequest, Body(...)],
) -> NovelResponse:
    novel_existing = repository_novel.get_by_id(id=id)
    if novel_existing.created_by != session_user.id:
        raise NotFoundException("Novel not found")

    supplied = body.model_fields_set - {"etag"}
    if not supplied:
        raise ValidationException("At least one property is required")

    for field in supplied:
        value = getattr(body, field)
        if field == "tags":
            value = list(value or [])
        setattr(novel_existing, field, value)

    novel_existing.updated_at = datetime.now(UTC)
    novel_existing.updated_by = session_user.id
    novel_return = repository_novel.update(novel_existing, body.etag)
    return to_novel_response(novel_return)


@router.delete("/{id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT, operation_id="delete_novel")
def delete_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    id: str,
) -> Response:
    novel_existing = repository_novel.get_by_id(id=id)
    if novel_existing.created_by != session_user.id:
        raise NotFoundException("Novel not found")
    repository_novel.delete(id=novel_existing.id, etag=None, deleted_by=session_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
