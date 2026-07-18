from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.injection import RepositoryUserDep
from app.core.security.authentication import hash_password
from app.core.security.authorization import ReqAdminUser
from app.domain.requests import UserCreateRequest, UserUpdateRequest, to_user_entity
from app.domain.responses import UserListResponse, UserResponse, to_user_response
from app.repositories.user_repository import (
    UserAlreadyExistsError,
    UserConflictError,
    UserNotFoundError,
)

router = APIRouter(prefix="/api/users", tags=["users"])

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_route(
    session_user: ReqAdminUser,
    repository_user: RepositoryUserDep,
    body: UserCreateRequest,
) -> UserResponse:
    
    try:
        user_entity = to_user_entity(body)
        user_entity.password_hash = hash_password(body.password)
        user_entity.created_by = session_user.id
        user_entity.updated_by = session_user.id
        user_return = repository_user.create(user_entity)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User email already exists",
        ) from exc
    return to_user_response(user_return)


@router.get("", response_model=UserListResponse)
def list_users_route(
    session_user: ReqAdminUser,
    repository_user: RepositoryUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    continuation_token: Annotated[str | None, Query(alias="continuationToken")] = None,
) -> UserListResponse:

    del session_user
    page = repository_user.list(limit=limit, continuation_token=continuation_token)
    return UserListResponse(
        items=[to_user_response(user) for user in page.items],
        continuation_token=page.continuation_token,
    )

@router.get("/{id}", response_model=UserResponse)
def get_user_route(
    session_user: ReqAdminUser,
    repository_user: RepositoryUserDep,
    id: str,
) -> UserResponse:

    del session_user
    try:
        user_return = repository_user.get_by_id(id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        ) from exc
    if user_return is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return to_user_response(user_return)


@router.patch("/{id}", response_model=UserResponse)
def update_user_route(
    session_user: ReqAdminUser,
    repository_user: RepositoryUserDep,
    id: str,
    body: UserUpdateRequest,
) -> UserResponse:

    try:
        existing_user = repository_user.get_by_id(id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        ) from exc
    if existing_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if "password" in body.model_fields_set and body.password is not None:
        existing_user.password_hash = hash_password(body.password)
    if "display_name" in body.model_fields_set:
        existing_user.display_name = body.display_name
    if "role" in body.model_fields_set and body.role is not None:
        existing_user.role = body.role
    if "status" in body.model_fields_set and body.status is not None:
        existing_user.status = body.status
    existing_user.updated_at = datetime.now(UTC)
    existing_user.updated_by = session_user.id

    try:
        user_return = repository_user.update(existing_user, body.etag)
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
    return to_user_response(user_return)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_route(
    session_user: ReqAdminUser,
    repository_user: RepositoryUserDep,
    id: str,
) -> Response:
    
    try:
        existing_user = repository_user.get_by_id(id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        ) from exc
    if existing_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
   
    if session_user.id == existing_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete current user",
        )
    
    try:
        repository_user.delete(
            id=existing_user.id,
            etag=None,
            deleted_by=session_user.id,
        )
    except UserConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="User has changed",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
