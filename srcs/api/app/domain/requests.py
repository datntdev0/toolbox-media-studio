"""Inbound request bodies."""

from datetime import datetime
from uuid import uuid4
from isodate import UTC
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.novels import NovelStatus
from app.domain.users import User, UserRole, UserStatus


class LoginRequest(BaseModel):
    """Credentials submitted to POST /auth/login."""

    email: EmailStr
    password: str


class UserCreateRequest(BaseModel):
    """Payload for creating a user."""

    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: str
    display_name: str | None = Field(default=None, alias="displayName")
    role: UserRole = UserRole.MEMBER
    status: UserStatus = UserStatus.ACTIVE


class UserUpdateRequest(BaseModel):
    """Payload for partially updating a user."""

    model_config = ConfigDict(populate_by_name=True)

    password: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")
    role: UserRole | None = None
    status: UserStatus | None = None
    etag: str | None = None


class NovelCreateRequest(BaseModel):
    """Payload for creating a novel."""

    model_config = ConfigDict(populate_by_name=True)

    title: str
    description: str | None = None
    cover_image_url: str | None = Field(default=None, alias="coverImageUrl")
    language: str | None = None
    author: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class NovelUpdateRequest(BaseModel):
    """Payload for partially updating a novel."""

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = None
    description: str | None = None
    cover_image_url: str | None = Field(default=None, alias="coverImageUrl")
    language: str | None = None
    author: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    status: NovelStatus | None = None


class CrawlerJobCreateRequest(BaseModel):
    """Payload for creating a crawler job."""

    model_config = ConfigDict(populate_by_name=True)

    url: str

def to_user_entity(body: UserCreateRequest) -> User:
    """Convert a UserCreateRequest to a User entity."""
    now = datetime.now(UTC)
    normalized_email = body.email.lower()
    return User(
        id=str(uuid4()),
        email=normalized_email,
        normalized_email=normalized_email,
        display_name=body.display_name,
        role=body.role,
        status=body.status,
        created_at=now,
        updated_at=now,
    )