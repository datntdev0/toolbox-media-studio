from fastapi import APIRouter, HTTPException, status
from app.core.exceptions import NotImplementException

from app.core.injection.service_provider import RepositoryUserDep
from app.core.security.authorization import SessionUser
from app.core.security.authentication import authenticate, InvalidCredentialsError
from app.domain.requests import LoginRequest
from app.domain.responses import TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, repositoryUser: RepositoryUserDep) -> TokenResponse:
    """Verify credentials and issue a JWT."""
    try:
        token = authenticate(body.email, body.password, repositoryUser)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        ) from exc
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me() -> UserResponse:
    """Return the current user resolved from the Bearer JWT."""
    raise NotImplementException("This endpoint is not yet implemented")
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        role=current_user.role,
        status=current_user.status,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        etag=current_user.etag,
    )
