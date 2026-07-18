from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from typing import Annotated

from app.core.injection.service_provider import RepositoryUserDep
from app.domain.users import User, UserRole
from app.core.security.jwt_helper import decode_access_token
from app.domain.users import UserStatus
_bearer_scheme = HTTPBearer(auto_error=False)

def get_session_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    repositoryUser: RepositoryUserDep,
) -> User:
    """Resolve the current user from a Bearer JWT, or raise 401."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or unauthorized",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise credentials_error

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError as exc:
        raise credentials_error from exc

    subject = payload.get("sub")
    if not subject:
        raise credentials_error

    user = repositoryUser.get_by_id(str(subject))
    if user is None or user.status != UserStatus.ACTIVE:
        raise credentials_error

    return user

SessionUser = Annotated[User, Depends(get_session_user)]

def require_admin_user(current_user: SessionUser) -> User:
    """Ensure the current user has an admin role, or raise 403."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    return current_user

ReqAdminUser = Annotated[User, Depends(require_admin_user)]