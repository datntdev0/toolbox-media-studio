import datetime
from jose import jwt
from typing import Any

from app.core.config.app_config import AppConfig

def create_access_token(subject: str, **claims: Any) -> str:
    """Create a signed JWT for the given subject."""
    settings = AppConfig()  # Singleton instance of AppSettings
    now = datetime.datetime.now(datetime.timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=settings.security.jwt_expire_minutes),
        **claims,
    }
    return jwt.encode(
        payload, settings.security.jwt_signing_key,
        algorithm=settings.security.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises JWTError if invalid or expired."""
    settings = AppConfig()  # Singleton instance of AppSettings
    return jwt.decode(
        token, settings.security.jwt_signing_key, 
        algorithms=[settings.security.jwt_algorithm])

