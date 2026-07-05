"""Outbound response models."""

from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Issued on successful login."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """The authenticated user, derived from the JWT."""

    email: str
    role: str
