"""JWT issuing/validation and password verification."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.core.config import Settings


def verify_password(plain: str, expected: str) -> bool:
    """Constant-time comparison of a plaintext password against the expected value.

    Credentials are supplied via config as plaintext this iteration, so we compare
    directly. When persistence is added this becomes a bcrypt hash verification.
    """
    return secrets.compare_digest(plain.encode(), expected.encode())


def create_access_token(subject: str, settings: Settings, **claims: Any) -> str:
    """Create a signed JWT for the given subject."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        **claims,
    }
    return jwt.encode(payload, settings.jwt_signing_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Decode and validate a JWT. Raises JWTError if invalid or expired."""
    return jwt.decode(token, settings.jwt_signing_key, algorithms=[settings.jwt_algorithm])


__all__ = [
    "JWTError",
    "create_access_token",
    "decode_access_token",
    "verify_password",
]
