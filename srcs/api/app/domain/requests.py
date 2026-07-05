"""Inbound request bodies."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Credentials submitted to POST /auth/login."""

    email: EmailStr
    password: str
