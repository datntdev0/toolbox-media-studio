"""User-management routes."""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Response, status

from app.core.dependencies import AdminUser, UserRepositoryDep
from app.domain.requests import UserCreateRequest, UserUpdateRequest
from app.domain.responses import UserListResponse, UserResponse
from app.repositories.user_repository import (
    UserAlreadyExistsError,
    UserConflictError,
    UserNotFoundError,
)
from app.routers.auth import to_user_response
from app.services.user_service import (
    CannotDeleteCurrentUserError,
    create_user,
    delete_user,
    get_user,
    list_users,
    update_user,
)

router = APIRouter(prefix="/api/users", tags=["users"])

IfMatchHeader = Annotated[str | None, Header(alias="If-Match")]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_route(
    body: UserCreateRequest,
    current_user: AdminUser,
    user_repository: UserRepositoryDep,
) -> UserResponse:
    """Create a new user."""

    try:
        user = create_user(body, current_user, user_repository)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User email already exists",
        ) from exc
    return to_user_response(user)


@router.get("", response_model=UserListResponse)
def list_users_route(
    current_user: AdminUser,
    user_repository: UserRepositoryDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    continuation_token: Annotated[str | None, Query(alias="continuationToken")] = None,
) -> UserListResponse:
    """List users."""

    del current_user
    page = list_users(user_repository, limit=limit, continuation_token=continuation_token)
    return UserListResponse(
        items=[to_user_response(user) for user in page.items],
        continuation_token=page.continuation_token,
    )


@router.get("/{id}", response_model=UserResponse)
def get_user_route(
    id: str,
    current_user: AdminUser,
    user_repository: UserRepositoryDep,
) -> UserResponse:
    """Fetch a user by id."""

    del current_user
    try:
        user = get_user(id, user_repository)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    return to_user_response(user)


@router.patch("/{id}", response_model=UserResponse)
def update_user_route(
    id: str,
    body: UserUpdateRequest,
    current_user: AdminUser,
    user_repository: UserRepositoryDep,
    if_match: IfMatchHeader = None,
) -> UserResponse:
    """Partially update a user."""

    try:
        user = update_user(id, body, current_user, user_repository, if_match)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User email already exists",
        ) from exc
    except UserConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="User has changed",
        ) from exc
    return to_user_response(user)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_route(
    id: str,
    current_user: AdminUser,
    user_repository: UserRepositoryDep,
    if_match: IfMatchHeader = None,
) -> Response:
    """Soft-delete a user."""

    try:
        delete_user(id, current_user, user_repository, if_match)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    except UserConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="User has changed",
        ) from exc
    except CannotDeleteCurrentUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete current user",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
