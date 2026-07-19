from fastapi import APIRouter, HTTPException, status

from app.core.injection import RepositoryUserDep
from app.core.security.authentication import InvalidCredentialsError, authenticate
from app.core.security.authorization import SessionUser
from app.domain.requests import LoginRequest
from app.domain.responses import TokenResponse, UserResponse, to_user_response

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, operation_id="login")
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


@router.get("/me", response_model=UserResponse, operation_id="me")
def me(current_user: SessionUser) -> UserResponse:
    """Return the current user resolved from the Bearer JWT."""
    return to_user_response(current_user)
