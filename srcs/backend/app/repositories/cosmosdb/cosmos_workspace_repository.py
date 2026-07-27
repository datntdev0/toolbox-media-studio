"""Azure Cosmos DB implementation of the workspace repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from azure.core import MatchConditions
from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.config.app_config import AppConfig
from app.domain.workspaces import Workspace, WorkspaceKind, WorkspacePage, WorkspaceStatus
from app.repositories.workspace_repository import (
    WorkspaceConflictError,
    WorkspaceNotFoundError,
)

WORKSPACES_CONTAINER_NAME = "domain.workspaces"


class CosmosWorkspaceRepository:
    """Workspace repository partitioned by project kind."""

    def __init__(self, client: CosmosClient, database_name: str) -> None:
        database = client.create_database_if_not_exists(id=database_name)
        self._container = database.create_container_if_not_exists(
            id=WORKSPACES_CONTAINER_NAME,
            partition_key=PartitionKey(path="/kind"),
        )

    def create(self, workspace: Workspace) -> Workspace:
        item = cast(
            dict[str, Any],
            self._container.create_item(body=self._serialize(workspace)),
        )
        return self._deserialize(item)

    def get_by_id(self, id: str) -> Workspace | None:
        items = list(
            self._container.query_items(
                query=(
                    "SELECT TOP 1 * FROM c "
                    "WHERE c.id = @id AND c.status != @deleted_status"
                ),
                parameters=[
                    {"name": "@id", "value": id},
                    {"name": "@deleted_status", "value": WorkspaceStatus.DELETED.value},
                ],
                enable_cross_partition_query=True,
            )
        )
        if not items:
            return None
        return self._deserialize(items[0])

    def list(
        self,
        kind: WorkspaceKind | None,
        limit: int,
        continuation_token: str | None,
    ) -> WorkspacePage:
        query = "SELECT * FROM c WHERE c.status != @deleted_status"
        parameters: list[dict[str, Any]] = [
            {"name": "@deleted_status", "value": WorkspaceStatus.DELETED.value}
        ]
        options: dict[str, Any] = {
            "max_item_count": limit,
            "parameters": parameters,
        }
        if kind is not None:
            query += " AND c.kind = @kind"
            parameters.append({"name": "@kind", "value": kind.value})
            options["partition_key"] = kind.value
        else:
            options["enable_cross_partition_query"] = True
        query += " ORDER BY c.updatedAt DESC"

        iterator = self._container.query_items(query=query, **options)
        page_iterator: Any = iterator.by_page(continuation_token=continuation_token)
        page = list(next(page_iterator, []))
        items = [self._deserialize(item) for item in page]
        return WorkspacePage(
            items=items,
            continuation_token=cast(str | None, page_iterator.continuation_token),
        )

    def update(self, workspace: Workspace, etag: str | None) -> Workspace:
        current = self.get_by_id(workspace.id)
        if current is None:
            raise WorkspaceNotFoundError
        if current.kind != workspace.kind:
            raise WorkspaceConflictError("Workspace kind cannot be changed")

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

    def delete(self, id: str, etag: str | None, deleted_by: str) -> None:
        workspace = self.get_by_id(id)
        if workspace is None:
            raise WorkspaceNotFoundError

        now = datetime.now(UTC)
        workspace.status = WorkspaceStatus.DELETED
        workspace.deleted_at = now
        workspace.deleted_by = deleted_by
        workspace.updated_at = now
        workspace.updated_by = deleted_by
        self.update(workspace, etag)

    @staticmethod
    def _serialize(workspace: Workspace) -> dict[str, Any]:
        return {
            "id": workspace.id,
            "name": workspace.name,
            "kind": workspace.kind.value,
            "novelId": workspace.novel_id,
            "targetLanguage": workspace.target_language,
            "status": workspace.status.value,
            "createdBy": workspace.created_by,
            "createdAt": workspace.created_at.isoformat(),
            "updatedBy": workspace.updated_by,
            "updatedAt": workspace.updated_at.isoformat(),
            "deletedAt": workspace.deleted_at.isoformat() if workspace.deleted_at else None,
            "deletedBy": workspace.deleted_by,
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> Workspace:
        return Workspace(
            id=cast(str, item["id"]),
            name=cast(str, item["name"]),
            kind=WorkspaceKind(cast(str, item["kind"])),
            novel_id=cast(str, item["novelId"]),
            target_language=cast(str, item["targetLanguage"]),
            status=WorkspaceStatus(cast(str, item["status"])),
            created_by=cast(str, item["createdBy"]),
            created_at=datetime.fromisoformat(cast(str, item["createdAt"])),
            updated_by=cast(str, item["updatedBy"]),
            updated_at=datetime.fromisoformat(cast(str, item["updatedAt"])),
            deleted_at=_optional_datetime(item.get("deletedAt")),
            deleted_by=cast(str | None, item.get("deletedBy")),
            etag=cast(str | None, item.get("_etag")),
        )


def build_cosmos_workspace_repository(config: AppConfig) -> CosmosWorkspaceRepository:
    """Construct the default Cosmos-backed workspace repository."""

    client = CosmosClient.from_connection_string(
        config.connectionStrings.azCosmosDb,
        connection_verify=True,
    )
    return CosmosWorkspaceRepository(client, config.azCosmosDbDatabaseName)


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(cast(str, value))
