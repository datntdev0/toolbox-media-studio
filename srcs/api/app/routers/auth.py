"""Authentication routes (FR-1)."""

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUser, SettingsDep, UserRepositoryDep
from app.domain.requests import LoginRequest
from app.domain.responses import TokenResponse, UserResponse
from app.domain.users import User
from app.services.auth_service import InvalidCredentialsError, authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    settings: SettingsDep,
    user_repository: UserRepositoryDep,
) -> TokenResponse:
    """Verify credentials and issue a JWT."""
    try:
        token = authenticate(body.email, body.password, settings, user_repository)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        ) from exc
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser) -> UserResponse:
    """Return the current user resolved from the Bearer JWT."""
    return to_user_response(current_user)


def to_user_response(user: User) -> UserResponse:
    """Map a stored user entity to the API response model."""

    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        etag=user.etag,
    )
