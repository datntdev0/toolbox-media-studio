"""Authentication routes (FR-1)."""

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUser, SettingsDep
from app.domain.requests import LoginRequest
from app.domain.responses import TokenResponse, UserResponse
from app.services.auth_service import InvalidCredentialsError, authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, settings: SettingsDep) -> TokenResponse:
    """Verify credentials and issue a JWT."""
    try:
        token = authenticate(body.email, body.password, settings)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        ) from exc
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser) -> UserResponse:
    """Return the current user resolved from the Bearer JWT."""
    return current_user
