"""User-management use-cases."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.domain.requests import UserCreateRequest, UserUpdateRequest
from app.domain.users import User, UserPage, UserRole, UserStatus
from app.repositories.user_repository import (
    UserAlreadyExistsError,
    UserConflictError,
    UserNotFoundError,
    UserRepository,
)

SEED_ACTOR = "seed"
logger = get_logger("user_service")


class CannotDeleteCurrentUserError(Exception):
    """Raised when an admin attempts to delete their own account."""


def create_user(
    body: UserCreateRequest,
    current_user: User,
    user_repository: UserRepository,
) -> User:
    """Create a new persisted user."""

    now = datetime.now(UTC)
    normalized_email = body.email.lower()
    user = User(
        id=str(uuid4()),
        email=normalized_email,
        normalized_email=normalized_email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role=body.role,
        status=body.status,
        created_by=current_user.id,
        created_at=now,
        updated_by=current_user.id,
        updated_at=now,
    )
    return user_repository.create(user)


def list_users(
    user_repository: UserRepository,
    limit: int,
    continuation_token: str | None,
) -> UserPage:
    """List persisted users."""

    return user_repository.list(limit=limit, continuation_token=continuation_token)


def get_user(id: str, user_repository: UserRepository) -> User:
    """Load a user by id or raise."""

    user = user_repository.get_by_id(id)
    if user is None:
        raise UserNotFoundError
    return user


def update_user(
    id: str,
    body: UserUpdateRequest,
    current_user: User,
    user_repository: UserRepository,
    etag: str | None,
) -> User:
    """Partially update a stored user."""

    user = get_user(id, user_repository)
    if "password" in body.model_fields_set and body.password is not None:
        user.password_hash = hash_password(body.password)
    if "display_name" in body.model_fields_set:
        user.display_name = body.display_name
    if "role" in body.model_fields_set and body.role is not None:
        user.role = body.role
    if "status" in body.model_fields_set and body.status is not None:
        user.status = body.status
    user.updated_at = datetime.now(UTC)
    user.updated_by = current_user.id
    return user_repository.update(user, etag)


def delete_user(
    id: str,
    current_user: User,
    user_repository: UserRepository,
    etag: str | None,
) -> None:
    """Soft-delete a user."""

    if id == current_user.id:
        raise CannotDeleteCurrentUserError
    user_repository.delete(id=id, etag=etag, deleted_by=current_user.id)


def seed_admin_user(settings: Settings, user_repository: UserRepository) -> User | None:
    """Seed the default admin user if it is missing."""

    logger.info(
        "Ensuring default admin user exists...",
        extra={"admin_email": settings.admin_email},
    )
    now = datetime.now(UTC)
    normalized_email = settings.admin_email.lower()
    seed_user = User(
        id=str(uuid4()),
        email=normalized_email,
        normalized_email=normalized_email,
        password_hash=hash_password(settings.admin_password),
        display_name="Admin",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        created_by=SEED_ACTOR,
        created_at=now,
        updated_by=SEED_ACTOR,
        updated_at=now,
    )
    created_user = user_repository.seed_admin(seed_user)
    return created_user


__all__ = [
    "CannotDeleteCurrentUserError",
    "UserAlreadyExistsError",
    "UserConflictError",
    "UserNotFoundError",
    "create_user",
    "delete_user",
    "get_user",
    "list_users",
    "seed_admin_user",
    "update_user",
]
