"""Media workspace CRUD routes."""

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Response, status

from app.core.injection import (
    PollingQueuePublisherDep,
    RealtimeHubDep,
    RepositoryWorkspaceDep,
    ServiceWorkspaceDep,
)
from app.core.security.authorization import SessionUser
from app.domain.requests import (
    WorkspaceCreateRequest,
    WorkspaceStartRequest,
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
from app.events.workspace_handler import (
    WORKSPACE_TASK_QUEUE_NAME,
    build_workspace_task_event,
    build_workspace_updated_payload,
)
from app.repositories.workspace_repository import (
    WorkspaceChapterRangeError,
    WorkspaceConflictError,
    WorkspaceContinuationTokenError,
    WorkspaceNotFoundError,
)
from app.services.novel_language_service import NovelLanguageNotFoundError
from app.services.workspace_service import WorkspaceSyncConflictError

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


@router.patch(
    "/{id}/start",
    response_model=WorkspaceDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="start_workspace",
)
def start_workspace_route(
    session_user: SessionUser,
    repository_workspace: RepositoryWorkspaceDep,
    service_workspace: ServiceWorkspaceDep,
    queue_publisher: PollingQueuePublisherDep,
    realtime_hub: RealtimeHubDep,
    id: str,
    body: WorkspaceStartRequest,
) -> WorkspaceDetailResponse:
    try:
        view = service_workspace.sync_tasks(id, updated_by=session_user.id)
    except (WorkspaceNotFoundError, NovelLanguageNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace or selected language not found",
        ) from exc
    except WorkspaceSyncConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    workspace = view.workspace
    for _ in range(3):
        try:
            queued = repository_workspace.queue_tasks(
                workspace.id,
                chapter_index_from=body.chapter_index_from,
                chapter_index_to=body.chapter_index_to,
                provider=body.provider,
                voice=body.voice,
                force=body.force,
                etag=workspace.etag,
            )
            break
        except WorkspaceConflictError:
            latest = repository_workspace.get_by_id(workspace.id)
            if latest is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workspace not found",
                ) from None
            workspace = latest
        except WorkspaceChapterRangeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace changed while tasks were being queued",
        )

    workspace = queued.workspace
    if queued.tasks:
        realtime_hub.publish(
            "workspace.updated",
            build_workspace_updated_payload(workspace),
        )
    try:
        for task in queued.tasks:
            queue_publisher.publish(
                WORKSPACE_TASK_QUEUE_NAME,
                build_workspace_task_event(workspace, task, refetch=body.refetch),
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Some workspace tasks could not be queued; retry with force",
        ) from exc
    refreshed = service_workspace.get_by_id(workspace.id)
    return to_workspace_detail_response(refreshed or view)


@router.patch(
    "/{id}/stop",
    response_model=WorkspaceDetailResponse,
    operation_id="stop_workspace",
)
def stop_workspace_route(
    session_user: SessionUser,
    repository_workspace: RepositoryWorkspaceDep,
    service_workspace: ServiceWorkspaceDep,
    realtime_hub: RealtimeHubDep,
    id: str,
) -> WorkspaceDetailResponse:
    del session_user
    workspace = repository_workspace.get_by_id(id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    for _ in range(3):
        try:
            updated = repository_workspace.stop_queued_tasks(
                workspace.id,
                etag=workspace.etag,
            )
            break
        except WorkspaceConflictError:
            latest = repository_workspace.get_by_id(workspace.id)
            if latest is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workspace not found",
                ) from None
            workspace = latest
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace changed while queued tasks were being stopped",
        )
    realtime_hub.publish(
        "workspace.updated",
        build_workspace_updated_payload(updated),
    )
    refreshed = service_workspace.get_by_id(updated.id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return to_workspace_detail_response(refreshed)


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
