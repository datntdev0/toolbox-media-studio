"""Inbound request bodies."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.novels import NovelStatus
from app.domain.users import UserRole, UserStatus


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
