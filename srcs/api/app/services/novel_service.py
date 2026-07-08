"""Novel-management use-cases."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.domain.novels import Novel, NovelPage, NovelStatus
from app.domain.requests import NovelCreateRequest, NovelUpdateRequest
from app.domain.users import User
from app.repositories.novel_repository import NovelNotFoundError, NovelRepository


def create_novel(
    body: NovelCreateRequest,
    current_user: User,
    novel_repository: NovelRepository,
) -> Novel:
    """Create a new persisted novel."""

    now = datetime.now(UTC)
    novel = Novel(
        id=str(uuid4()),
        title=body.title,
        description=body.description,
        cover_image_url=body.cover_image_url,
        language=body.language,
        author=body.author,
        tags=list(body.tags or []),
        notes=body.notes,
        status=NovelStatus.DRAFT,
        created_by=current_user.id,
        created_at=now,
        updated_by=current_user.id,
        updated_at=now,
    )
    return novel_repository.create(novel)


def list_novels(
    current_user: User,
    novel_repository: NovelRepository,
    limit: int,
    continuation_token: str | None,
) -> NovelPage:
    """List persisted novels for the current user."""

    return novel_repository.list(
        created_by=current_user.id,
        limit=limit,
        continuation_token=continuation_token,
    )


def get_novel(id: str, current_user: User, novel_repository: NovelRepository) -> Novel:
    """Load a novel by id within the current user's scope or raise."""

    novel = novel_repository.get_by_id(id=id, created_by=current_user.id)
    if novel is None:
        raise NovelNotFoundError
    return novel


def update_novel(
    id: str,
    body: NovelUpdateRequest,
    current_user: User,
    novel_repository: NovelRepository,
    etag: str | None,
) -> Novel:
    """Partially update a stored novel."""

    novel = get_novel(id, current_user, novel_repository)
    if "title" in body.model_fields_set and body.title is not None:
        novel.title = body.title
    if "description" in body.model_fields_set:
        novel.description = body.description
    if "cover_image_url" in body.model_fields_set:
        novel.cover_image_url = body.cover_image_url
    if "language" in body.model_fields_set:
        novel.language = body.language
    if "author" in body.model_fields_set:
        novel.author = body.author
    if "tags" in body.model_fields_set:
        novel.tags = list(body.tags or [])
    if "notes" in body.model_fields_set:
        novel.notes = body.notes
    if "status" in body.model_fields_set and body.status is not None:
        novel.status = body.status
    novel.updated_at = datetime.now(UTC)
    novel.updated_by = current_user.id
    return novel_repository.update(novel, etag)


def delete_novel(
    id: str,
    current_user: User,
    novel_repository: NovelRepository,
    etag: str | None,
) -> None:
    """Soft-delete a stored novel."""

    novel_repository.delete(
        id=id,
        created_by=current_user.id,
        etag=etag,
        deleted_by=current_user.id,
    )
