"""Azure Cosmos DB workspace repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from azure.core import MatchConditions
from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.config.app_config import AppConfig
from app.domain.workspaces import (
    Workspace,
    WorkspacePage,
    WorkspaceProgress,
    WorkspaceQueueResult,
    WorkspaceTask,
    WorkspaceTaskStatus,
    WorkspaceType,
)
from app.repositories.workspace_repository import (
    WorkspaceChapterRangeError,
    WorkspaceConflictError,
    WorkspaceContinuationTokenError,
    WorkspaceNotFoundError,
)

WORKSPACES_CONTAINER_NAME = "domain.workspaces"


class CosmosWorkspaceRepository:
    """Workspace repository partitioned by workspace identifier."""

    def __init__(self, client: CosmosClient, database_name: str) -> None:
        database = client.create_database_if_not_exists(id=database_name)
        self._container = database.create_container_if_not_exists(
            id=WORKSPACES_CONTAINER_NAME,
            partition_key=PartitionKey(path="/id"),
        )

    def create(self, workspace: Workspace) -> Workspace:
        item = cast(
            dict[str, Any],
            self._container.create_item(body=self._serialize(workspace)),
        )
        return self._deserialize(item)

    def get_by_id(self, id: str) -> Workspace | None:
        try:
            item = cast(
                dict[str, Any],
                self._container.read_item(item=id, partition_key=id),
            )
        except exceptions.CosmosResourceNotFoundError:
            return None
        workspace = self._deserialize(item)
        return None if workspace.deleted_at is not None else workspace

    def list(
        self,
        workspace_type: WorkspaceType | None,
        limit: int,
        continuation_token: str | None,
    ) -> WorkspacePage:
        clauses = ["(NOT IS_DEFINED(c.deletedAt) OR IS_NULL(c.deletedAt))"]
        parameters: list[dict[str, Any]] = []
        if workspace_type is not None:
            clauses.append("c.type = @workspace_type")
            parameters.append(
                {"name": "@workspace_type", "value": workspace_type.value}
            )
        query = f"SELECT * FROM c WHERE {' AND '.join(clauses)} ORDER BY c.updatedAt DESC"
        iterator = self._container.query_items(
            query=query,
            parameters=parameters,
            max_item_count=limit,
            enable_cross_partition_query=True,
        )
        page_iterator: Any = iterator.by_page(continuation_token=continuation_token)
        try:
            page = list(next(page_iterator, []))
        except exceptions.CosmosHttpResponseError as exc:
            if exc.status_code == 400:
                raise WorkspaceContinuationTokenError(
                    "Invalid continuation token"
                ) from exc
            raise
        return WorkspacePage(
            items=[self._deserialize(item) for item in page],
            continuation_token=cast(str | None, page_iterator.continuation_token),
        )

    def update(self, workspace: Workspace, etag: str | None = None) -> Workspace:
        if self.get_by_id(workspace.id) is None:
            raise WorkspaceNotFoundError
        options: dict[str, Any] = {}
        if etag is not None:
            options["etag"] = etag
            options["match_condition"] = MatchConditions.IfNotModified
        try:
            item = cast(
                dict[str, Any],
                self._container.replace_item(
                    item=workspace.id,
                    body=self._serialize(workspace),
                    **options,
                ),
            )
        except exceptions.CosmosAccessConditionFailedError as exc:
            raise WorkspaceConflictError("Workspace has changed") from exc
        except exceptions.CosmosResourceNotFoundError as exc:
            raise WorkspaceNotFoundError from exc
        return self._deserialize(item)

    def delete(self, id: str, deleted_by: str) -> None:
        workspace = self.get_by_id(id)
        if workspace is None:
            raise WorkspaceNotFoundError
        now = datetime.now(UTC)
        workspace.deleted_at = now
        workspace.deleted_by = deleted_by
        workspace.updated_at = now
        workspace.updated_by = deleted_by
        self.update(workspace, workspace.etag)

    def queue_tasks(
        self,
        id: str,
        *,
        chapter_index_from: int,
        chapter_index_to: int,
        provider: str,
        voice: str,
        force: bool,
        etag: str | None,
    ) -> WorkspaceQueueResult:
        workspace = self._require(id)
        self._check_etag(workspace, etag)
        matching = [
            task
            for task in workspace.tasks
            if not task.source_removed
            and chapter_index_from <= task.manifest_index + 1 <= chapter_index_to
        ]
        if not matching:
            raise WorkspaceChapterRangeError(
                "No workspace tasks match the requested chapter index range"
            )
        queued = [
            task
            for task in matching
            if force
            or task.status not in {WorkspaceTaskStatus.QUEUED, WorkspaceTaskStatus.RUNNING}
        ]
        if not queued:
            return WorkspaceQueueResult(workspace=workspace, tasks=[])
        queued_ids = {task.id for task in queued}
        for task in queued:
            task.status = WorkspaceTaskStatus.QUEUED
            task.last_error = None
            task.provider = provider
            task.voice = voice
        self._touch(workspace)
        updated = self.update(workspace, etag or workspace.etag)
        return WorkspaceQueueResult(
            workspace=updated,
            tasks=[task for task in updated.tasks if task.id in queued_ids],
        )

    def stop_queued_tasks(self, id: str, *, etag: str | None) -> Workspace:
        workspace = self._require(id)
        self._check_etag(workspace, etag)
        for task in workspace.tasks:
            if task.status == WorkspaceTaskStatus.QUEUED:
                task.status = WorkspaceTaskStatus.CREATED
        self._touch(workspace)
        return self.update(workspace, etag or workspace.etag)

    def claim_task(
        self,
        id: str,
        task_id: str,
        *,
        etag: str | None,
    ) -> Workspace | None:
        workspace = self._require(id)
        self._check_etag(workspace, etag)
        task = self._require_task(workspace, task_id)
        if task.source_removed or task.status != WorkspaceTaskStatus.QUEUED:
            return None
        task.status = WorkspaceTaskStatus.RUNNING
        task.attempts += 1
        task.last_error = None
        self._touch(workspace)
        return self.update(workspace, etag or workspace.etag)

    def update_task(
        self,
        id: str,
        task_id: str,
        status: WorkspaceTaskStatus,
        *,
        attempts: int,
        error: str | None,
        result_available: bool,
        completed_at: datetime | None,
        source_chapter_updated_at: datetime | None,
        clear_source_updated: bool,
        etag: str | None,
    ) -> Workspace:
        workspace = self._require(id)
        self._check_etag(workspace, etag)
        task = self._require_task(workspace, task_id)
        task.status = status
        task.attempts = max(task.attempts, attempts)
        task.last_error = error
        task.result_available = result_available
        task.completed_at = completed_at
        if source_chapter_updated_at is not None:
            task.source_chapter_updated_at = source_chapter_updated_at
        if clear_source_updated:
            task.source_updated = False
        self._touch(workspace)
        return self.update(workspace, etag or workspace.etag)

    def _require(self, id: str) -> Workspace:
        workspace = self.get_by_id(id)
        if workspace is None:
            raise WorkspaceNotFoundError
        return workspace

    @staticmethod
    def _require_task(workspace: Workspace, task_id: str) -> WorkspaceTask:
        task = next((item for item in workspace.tasks if item.id == task_id), None)
        if task is None:
            raise WorkspaceNotFoundError
        return task

    @staticmethod
    def _check_etag(workspace: Workspace, etag: str | None) -> None:
        if etag is not None and workspace.etag != etag:
            raise WorkspaceConflictError("Workspace has changed")

    @staticmethod
    def _touch(workspace: Workspace) -> None:
        workspace.progress = WorkspaceProgress.from_tasks(workspace.tasks)
        workspace.updated_at = datetime.now(UTC)

    @staticmethod
    def _serialize(workspace: Workspace) -> dict[str, Any]:
        return {
            "id": workspace.id,
            "title": workspace.title,
            "type": workspace.type.value,
            "novelId": workspace.novel_id,
            "language": workspace.language,
            "createdBy": workspace.created_by,
            "createdAt": workspace.created_at.isoformat(),
            "updatedBy": workspace.updated_by,
            "updatedAt": workspace.updated_at.isoformat(),
            "tasks": [_serialize_task(task) for task in workspace.tasks],
            "progress": _serialize_progress(workspace.progress),
            "deletedAt": (
                workspace.deleted_at.isoformat() if workspace.deleted_at else None
            ),
            "deletedBy": workspace.deleted_by,
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> Workspace:
        return Workspace(
            id=cast(str, item["id"]),
            title=cast(str, item["title"]),
            type=WorkspaceType(cast(str, item["type"])),
            novel_id=cast(str, item["novelId"]),
            language=cast(str, item["language"]),
            created_by=cast(str, item["createdBy"]),
            created_at=datetime.fromisoformat(cast(str, item["createdAt"])),
            updated_by=cast(str, item["updatedBy"]),
            updated_at=datetime.fromisoformat(cast(str, item["updatedAt"])),
            tasks=[
                _deserialize_task(task)
                for task in cast(list[dict[str, Any]], item.get("tasks", []))
            ],
            progress=_deserialize_progress(item.get("progress")),
            deleted_at=_parse_datetime(item.get("deletedAt")),
            deleted_by=cast(str | None, item.get("deletedBy")),
            etag=cast(str | None, item.get("_etag")),
        )


def build_cosmos_workspace_repository(config: AppConfig) -> CosmosWorkspaceRepository:
    client = CosmosClient.from_connection_string(
        config.connectionStrings.azCosmosDb,
        connection_verify=config.environment.lower() != "localhost",
    )
    return CosmosWorkspaceRepository(client, config.azCosmosDbDatabaseName)


def _parse_datetime(value: Any) -> datetime | None:
    return datetime.fromisoformat(value) if isinstance(value, str) else None


def _serialize_task(task: WorkspaceTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "chapterNumber": task.chapter_number,
        "manifestIndex": task.manifest_index,
        "sourceChapterUpdatedAt": task.source_chapter_updated_at.isoformat(),
        "status": task.status.value,
        "attempts": task.attempts,
        "lastError": task.last_error,
        "resultAvailable": task.result_available,
        "completedAt": task.completed_at.isoformat() if task.completed_at else None,
        "sourceUpdated": task.source_updated,
        "sourceRemoved": task.source_removed,
        "provider": task.provider,
        "voice": task.voice,
    }


def _deserialize_task(item: dict[str, Any]) -> WorkspaceTask:
    return WorkspaceTask(
        id=cast(str, item["id"]),
        title=cast(str, item["title"]),
        chapter_number=cast(int | None, item.get("chapterNumber")),
        manifest_index=cast(int, item["manifestIndex"]),
        source_chapter_updated_at=datetime.fromisoformat(
            cast(str, item["sourceChapterUpdatedAt"])
        ),
        status=WorkspaceTaskStatus(
            cast(str, item.get("status", WorkspaceTaskStatus.CREATED.value))
        ),
        attempts=cast(int, item.get("attempts", 0)),
        last_error=cast(str | None, item.get("lastError")),
        result_available=cast(bool, item.get("resultAvailable", False)),
        completed_at=_parse_datetime(item.get("completedAt")),
        source_updated=cast(bool, item.get("sourceUpdated", False)),
        source_removed=cast(bool, item.get("sourceRemoved", False)),
        provider=cast(str | None, item.get("provider")),
        voice=cast(str | None, item.get("voice")),
    )


def _serialize_progress(progress: WorkspaceProgress) -> dict[str, int]:
    return {
        "total": progress.total,
        "created": progress.created,
        "queued": progress.queued,
        "running": progress.running,
        "completed": progress.completed,
        "failed": progress.failed,
    }


def _deserialize_progress(value: Any) -> WorkspaceProgress:
    if not isinstance(value, dict):
        return WorkspaceProgress()
    return WorkspaceProgress(
        total=int(value.get("total", 0)),
        created=int(value.get("created", 0)),
        queued=int(value.get("queued", 0)),
        running=int(value.get("running", 0)),
        completed=int(value.get("completed", 0)),
        failed=int(value.get("failed", 0)),
    )
