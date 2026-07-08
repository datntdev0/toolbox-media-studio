"""Shared FastAPI dependencies."""

from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.security import JWTError, decode_access_token
from app.repositories.novel_repository import NovelRepository
from app.domain.users import User, UserRole, UserStatus
from app.repositories.user_repository import UserRepository

SettingsDep = Annotated[Settings, Depends(get_settings)]

_bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(request: Request) -> UserRepository:
    """Resolve the configured user repository from app state."""

    repository = getattr(request.app.state, "user_repository", None)
    if repository is None:
        raise RuntimeError("User repository is not configured")
    return cast(UserRepository, repository)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


def get_novel_repository(request: Request) -> NovelRepository:
    """Resolve the configured novel repository from app state."""

    repository = getattr(request.app.state, "novel_repository", None)
    if repository is None:
        raise RuntimeError("Novel repository is not configured")
    return cast(NovelRepository, repository)


NovelRepositoryDep = Annotated[NovelRepository, Depends(get_novel_repository)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    settings: SettingsDep,
    user_repository: UserRepositoryDep,
) -> User:
    """Resolve the current user from a Bearer JWT, or raise 401."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise credentials_error

    try:
        payload = decode_access_token(credentials.credentials, settings)
    except JWTError as exc:
        raise credentials_error from exc

    subject = payload.get("sub")
    if not subject:
        raise credentials_error

    user = user_repository.get_by_id(str(subject))
    if user is None or user.status != UserStatus.ACTIVE:
        raise credentials_error

    return user


def require_admin_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Ensure the current user has admin privileges."""

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin_user)]
