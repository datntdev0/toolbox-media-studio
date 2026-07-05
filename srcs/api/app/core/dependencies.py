"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import Settings, get_settings
from app.core.security import JWTError, decode_access_token
from app.domain.responses import UserResponse

SettingsDep = Annotated[Settings, Depends(get_settings)]

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(
    token: Annotated[str, Depends(_oauth2_scheme)],
    settings: SettingsDep,
) -> UserResponse:
    """Resolve the current user from a Bearer JWT, or raise 401."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token, settings)
    except JWTError as exc:
        raise credentials_error from exc

    email = payload.get("sub")
    role = payload.get("role")
    if not email or not role:
        raise credentials_error

    return UserResponse(email=email, role=role)


CurrentUser = Annotated[UserResponse, Depends(get_current_user)]
