"""Novel-management routes."""

# ruff: noqa: E501

import json
import unicodedata
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path as FilePath
from typing import Annotated
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Body, File, Path, Query, Response, UploadFile, status

from app.core.exceptions import NotFoundException, StateConflictException, ValidationException
from app.core.injection import (
    ProviderPublicBlobDep,
    RepositoryNovelChapterDep,
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

_NOVEL_CONTEXT_DIRECTORY = FilePath(__file__).resolve().parents[1] / "skills" / "novel-context"

_WINDOWS_RESERVED_FILENAMES = {
    "aux",
    "com1",
    "com2",
    "com3",
    "com4",
    "com5",
    "com6",
    "com7",
    "com8",
    "com9",
    "con",
    "lpt1",
    "lpt2",
    "lpt3",
    "lpt4",
    "lpt5",
    "lpt6",
    "lpt7",
    "lpt8",
    "lpt9",
    "nul",
    "prn",
}


def _sanitize_export_filename(value: str, *, fallback: str) -> str:
    """Return a portable, non-empty filename stem for a ZIP entry or download."""

    normalized = unicodedata.normalize("NFKC", value)
    sanitized = "".join(
        "_"
        if character in '<>:"/\\|?*' or ord(character) < 32 or ord(character) == 127
        else character
        for character in normalized
    ).strip(". ")
    sanitized = sanitized[:100].rstrip(". ")
    if not sanitized:
        sanitized = fallback
    if sanitized.casefold() in _WINDOWS_RESERVED_FILENAMES:
        sanitized = f"{sanitized}_"
    return sanitized


def _chapter_export_filename(title: str, position: int, used_stems: set[str]) -> str:
    """Build a reading-order-prefixed, unique text filename for one chapter."""

    stem = _sanitize_export_filename(title, fallback="chapter")
    candidate = stem
    suffix_number = 2
    while candidate.casefold() in used_stems:
        suffix = f"_{suffix_number}"
        candidate = f"{stem[: 100 - len(suffix)].rstrip('. ')}{suffix}"
        suffix_number += 1
    used_stems.add(candidate.casefold())
    return f"{position:03d} - {candidate}.txt"


def _content_disposition_for_export(title: str) -> str:
    """Return a CRLF-safe disposition header with an ASCII fallback and UTF-8 name."""

    filename_stem = _sanitize_export_filename(title, fallback="novel")
    ascii_stem = (
        unicodedata.normalize("NFKD", filename_stem).encode("ascii", "ignore").decode()
    )
    ascii_stem = _sanitize_export_filename(ascii_stem, fallback="novel")
    filename = f"{filename_stem}.zip"
    return f"attachment; filename=\"{ascii_stem}.zip\"; filename*=UTF-8''{quote(filename, safe='')}"


def _write_novel_context_files(archive: ZipFile) -> None:
    """Append the packaged novel-context files to the archive root."""

    for context_file in sorted(_NOVEL_CONTEXT_DIRECTORY.iterdir(), key=lambda item: item.name.casefold()):
        if context_file.is_file() and not context_file.is_symlink():
            archive.writestr(context_file.name, context_file.read_bytes())


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
    if novel_return.created_by != session_user.id:
        raise NotFoundException("Novel not found")
    novel_return, chapters = binding_service.get_detail(id)
    return to_novel_detail_response(novel_return, chapters)


@router.get("/{id}/export", response_model=None, response_class=Response, status_code=status.HTTP_200_OK, operation_id="export_novel", responses={200: {"content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}}, "description": "ZIP archive containing novel metadata and chapters."}})
def export_novel_route(
    session_user: SessionUser,
    repository_novel: RepositoryNovelDep,
    repository_novel_chapter: RepositoryNovelChapterDep,
    id: str,
) -> Response:
    """Export an owned novel and all of its chapters as an in-memory ZIP archive."""

    novel = repository_novel.get_by_id(id=id)
    if novel.created_by != session_user.id:
        raise NotFoundException("Novel not found")

    chapters = sorted(
        repository_novel_chapter.list(novel.id).items,
        key=lambda chapter: (chapter.manifest_index, chapter.id),
    )
    used_stems: set[str] = set()
    with BytesIO() as buffer:
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            metadata = to_novel_response(novel).model_dump(by_alias=True, mode="json")
            archive.writestr(
                "novel.json",
                json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
            )
            for position, chapter in enumerate(chapters, start=1):
                archive.writestr(
                    _chapter_export_filename(chapter.title, position, used_stems),
                    ("\n\n".join(chapter.content) if chapter.content_available else "").encode(
                        "utf-8"
                    ),
                )
            _write_novel_context_files(archive)
        archive_bytes = buffer.getvalue()

    return Response(
        content=archive_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": _content_disposition_for_export(novel.title)},
    )


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
