"""Outbound response models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.users import UserRole, UserStatus


class TokenResponse(BaseModel):
    """Issued on successful login."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User payload returned by auth and user-management endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    email: str
    display_name: str | None = Field(default=None, alias="displayName")
    role: UserRole
    status: UserStatus
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    etag: str | None = None


class UserListResponse(BaseModel):
    """Paged response for listing users."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[UserResponse]
    continuation_token: str | None = Field(default=None, alias="continuationToken")
