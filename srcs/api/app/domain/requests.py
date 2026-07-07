"""Inbound request bodies."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
