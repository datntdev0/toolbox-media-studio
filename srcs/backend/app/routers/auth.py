from fastapi import APIRouter, status

from app.core.injection import RepositoryUserDep
from app.core.security.authentication import authenticate
from app.core.security.authorization import SessionUser
from app.domain.requests import LoginRequest
from app.domain.responses import TokenResponse, UserResponse, to_user_response

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    operation_id="login",
)
def login_route(
    repository_user: RepositoryUserDep,
    body: LoginRequest,
) -> TokenResponse:
    """Verify credentials and issue a JWT."""
    token = authenticate(body.email, body.password, repository_user)
    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    operation_id="me",
)
def me_route(current_user: SessionUser) -> UserResponse:
    """Return the current user resolved from the Bearer JWT."""
    return to_user_response(current_user)
