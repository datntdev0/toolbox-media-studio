"""Workspace-management routes."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Response, status

from app.core.injection import RepositoryNovelDep, RepositoryWorkspaceDep
from app.core.security.authorization import SessionUser
from app.domain.requests import (
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
    to_workspace_entity,
)
from app.domain.responses import (
    WorkspaceListResponse,
    WorkspaceResponse,
    to_workspace_response,
)
from app.domain.workspaces import WorkspaceKind
from app.repositories.workspace_repository import (
    WorkspaceConflictError,
    WorkspaceContinuationTokenError,
    WorkspaceNotFoundError,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_workspace",
)
def create_workspace_route(
    session_user: SessionUser,
    repository_workspace: RepositoryWorkspaceDep,
    repository_novel: RepositoryNovelDep,
    body: Annotated[WorkspaceCreateRequest, Body(...)],
) -> WorkspaceResponse:
    novel = repository_novel.get_by_id(body.novel_id)
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found")

    workspace = repository_workspace.create(to_workspace_entity(body, session_user.id))
    return to_workspace_response(workspace, novel)


@router.get("", response_model=WorkspaceListResponse, operation_id="list_workspaces")
def list_workspaces_route(
    session_user: SessionUser,
    repository_workspace: RepositoryWorkspaceDep,
    repository_novel: RepositoryNovelDep,
    kind: WorkspaceKind | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    continuation_token: Annotated[str | None, Query(alias="continuationToken")] = None,
) -> WorkspaceListResponse:
    del session_user
    try:
        page = repository_workspace.list(kind, limit, continuation_token)
    except WorkspaceContinuationTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return WorkspaceListResponse(
        items=[
            to_workspace_response(
                workspace,
                repository_novel.get_by_id(workspace.novel_id),
            )
            for workspace in page.items
        ],
        continuation_token=page.continuation_token,
    )


@router.get("/{id}", response_model=WorkspaceResponse, operation_id="get_workspace")
def get_workspace_route(
    session_user: SessionUser,
    repository_workspace: RepositoryWorkspaceDep,
    repository_novel: RepositoryNovelDep,
    id: str,
) -> WorkspaceResponse:
    del session_user
    workspace = repository_workspace.get_by_id(id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return to_workspace_response(workspace, repository_novel.get_by_id(workspace.novel_id))


@router.put("/{id}", response_model=WorkspaceResponse, operation_id="update_workspace")
def update_workspace_route(
    session_user: SessionUser,
    repository_workspace: RepositoryWorkspaceDep,
    repository_novel: RepositoryNovelDep,
    id: str,
    body: Annotated[WorkspaceUpdateRequest, Body(...)],
) -> WorkspaceResponse:
    workspace = repository_workspace.get_by_id(id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    novel = repository_novel.get_by_id(body.novel_id)
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found")

    workspace.name = body.name.strip()
    workspace.novel_id = body.novel_id
    workspace.target_language = body.target_language.strip()
    workspace.updated_at = datetime.now(UTC)
    workspace.updated_by = session_user.id
    try:
        updated = repository_workspace.update(workspace, body.etag)
    except WorkspaceConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        ) from exc
    return to_workspace_response(updated, novel)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_workspace",
)
def delete_workspace_route(
    session_user: SessionUser,
    repository_workspace: RepositoryWorkspaceDep,
    id: str,
) -> Response:
    if repository_workspace.get_by_id(id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    try:
        repository_workspace.delete(id, etag=None, deleted_by=session_user.id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        ) from exc
    except WorkspaceConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
