"""Azure Cosmos DB workspace repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.config.app_config import AppConfig
from app.domain.workspaces import Workspace, WorkspacePage, WorkspaceType
from app.repositories.workspace_repository import (
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

    def update(self, workspace: Workspace) -> Workspace:
        if self.get_by_id(workspace.id) is None:
            raise WorkspaceNotFoundError
        try:
            item = cast(
                dict[str, Any],
                self._container.replace_item(
                    item=workspace.id,
                    body=self._serialize(workspace),
                ),
            )
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
        self.update(workspace)

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
