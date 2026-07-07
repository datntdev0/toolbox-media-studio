"""Authentication use-cases backed by the user repository."""

from app.core.config import Settings
from app.core.security import create_access_token, verify_password
from app.domain.users import UserStatus
from app.repositories.user_repository import UserRepository


class InvalidCredentialsError(Exception):
    """Raised when login credentials are invalid."""


def authenticate(
    email: str,
    password: str,
    settings: Settings,
    user_repository: UserRepository,
) -> str:
    """Validate credentials against the user store and return a signed JWT."""

    user = user_repository.get_by_email(email)
    if user is None or user.status != UserStatus.ACTIVE:
        raise InvalidCredentialsError
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError

    return create_access_token(
        subject=user.id,
        settings=settings,
        email=user.email,
        role=user.role.value,
    )
