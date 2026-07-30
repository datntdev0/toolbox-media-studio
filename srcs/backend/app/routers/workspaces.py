"""Media workspace CRUD routes."""

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Response, status

from app.core.injection import ServiceWorkspaceDep
from app.core.security.authorization import SessionUser
from app.domain.requests import (
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
    to_workspace_entity,
)
from app.domain.responses import (
    WorkspaceDetailResponse,
    WorkspaceListResponse,
    WorkspaceResponse,
    to_workspace_detail_response,
    to_workspace_response,
)
from app.domain.workspaces import WorkspaceType
from app.repositories.workspace_repository import (
    WorkspaceContinuationTokenError,
    WorkspaceNotFoundError,
)
from app.services.novel_language_service import NovelLanguageNotFoundError

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_workspace",
)
def create_workspace_route(
    session_user: SessionUser,
    service_workspace: ServiceWorkspaceDep,
    body: Annotated[WorkspaceCreateRequest, Body(...)],
) -> WorkspaceResponse:
    try:
        view = service_workspace.create(to_workspace_entity(body, session_user.id))
    except NovelLanguageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return to_workspace_response(view)


@router.get(
    "",
    response_model=WorkspaceListResponse,
    operation_id="list_workspaces",
)
def list_workspaces_route(
    session_user: SessionUser,
    service_workspace: ServiceWorkspaceDep,
    workspace_type: Annotated[WorkspaceType | None, Query(alias="type")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    continuation_token: Annotated[str | None, Query(alias="continuationToken")] = None,
) -> WorkspaceListResponse:
    del session_user
    try:
        items, next_token = service_workspace.list(
            workspace_type,
            limit,
            continuation_token,
        )
    except WorkspaceContinuationTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return WorkspaceListResponse(
        items=[to_workspace_response(item) for item in items],
        continuation_token=next_token,
    )


@router.get(
    "/{id}",
    response_model=WorkspaceDetailResponse,
    operation_id="get_workspace",
)
def get_workspace_route(
    session_user: SessionUser,
    service_workspace: ServiceWorkspaceDep,
    id: str,
) -> WorkspaceDetailResponse:
    del session_user
    try:
        view = service_workspace.get_by_id(id)
    except NovelLanguageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return to_workspace_detail_response(view)


@router.put(
    "/{id}",
    response_model=WorkspaceResponse,
    operation_id="update_workspace",
)
def update_workspace_route(
    session_user: SessionUser,
    service_workspace: ServiceWorkspaceDep,
    id: str,
    body: Annotated[WorkspaceUpdateRequest, Body(...)],
) -> WorkspaceResponse:
    try:
        return to_workspace_response(
            service_workspace.update(id, body.title, session_user.id)
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        ) from exc


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_workspace",
)
def delete_workspace_route(
    session_user: SessionUser,
    service_workspace: ServiceWorkspaceDep,
    id: str,
) -> Response:
    try:
        service_workspace.delete(id, session_user.id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
