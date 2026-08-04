"""Azure Cosmos DB implementation of workspace task results."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.config.app_config import AppConfig
from app.domain.workspace_results import WorkspaceResult

WORKSPACE_RESULTS_CONTAINER_NAME = "domain.workspace_results"


class CosmosWorkspaceResultRepository:
    """WorkspaceResult repository partitioned by workspace ID."""

    def __init__(self, client: CosmosClient, database_name: str) -> None:
        database = client.create_database_if_not_exists(id=database_name)
        self._container = database.create_container_if_not_exists(
            id=WORKSPACE_RESULTS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/workspaceId"),
        )

    def get(self, workspace_id: str, task_id: str) -> WorkspaceResult | None:
        try:
            item = cast(
                dict[str, Any],
                self._container.read_item(item=task_id, partition_key=workspace_id),
            )
        except exceptions.CosmosResourceNotFoundError:
            return None
        return self._deserialize(item)

    def upsert(self, result: WorkspaceResult) -> WorkspaceResult:
        if result.id != result.task_id:
            raise ValueError("WorkspaceResult id must equal taskId")
        current = self.get(result.workspace_id, result.task_id)
        if current is not None:
            result.created_at = current.created_at
        result.updated_at = datetime.now(UTC)
        item = cast(
            dict[str, Any],
            self._container.upsert_item(body=self._serialize(result)),
        )
        return self._deserialize(item)

    def delete_by_workspace(self, workspace_id: str) -> None:
        task_ids = list(
            self._container.query_items(
                query="SELECT VALUE c.id FROM c WHERE c.workspaceId = @workspace_id",
                parameters=[{"name": "@workspace_id", "value": workspace_id}],
                partition_key=workspace_id,
            )
        )
        for task_id in task_ids:
            try:
                self._container.delete_item(item=cast(str, task_id), partition_key=workspace_id)
            except exceptions.CosmosResourceNotFoundError:
                continue

    @staticmethod
    def _serialize(result: WorkspaceResult) -> dict[str, Any]:
        return {
            "id": result.task_id,
            "workspaceId": result.workspace_id,
            "taskId": result.task_id,
            "provider": result.provider,
            "voice": result.voice,
            "schemaVersion": result.schema_version,
            "contentKey": result.content_key,
            "audioUrl": result.audio_url,
            "subtitleUrl": result.subtitle_url,
            "createdAt": result.created_at.isoformat(),
            "updatedAt": result.updated_at.isoformat(),
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> WorkspaceResult:
        return WorkspaceResult(
            id=cast(str, item["id"]),
            workspace_id=cast(str, item["workspaceId"]),
            task_id=cast(str, item["taskId"]),
            provider=cast(str, item["provider"]),
            voice=cast(str, item["voice"]),
            schema_version=cast(int, item.get("schemaVersion", 1)),
            content_key=list(cast(list[str], item.get("contentKey", []))),
            audio_url=cast(str | None, item.get("audioUrl")),
            subtitle_url=cast(str | None, item.get("subtitleUrl")),
            created_at=datetime.fromisoformat(cast(str, item["createdAt"])),
            updated_at=datetime.fromisoformat(cast(str, item["updatedAt"])),
            etag=cast(str | None, item.get("_etag")),
        )


def build_cosmos_workspace_result_repository(
    config: AppConfig,
) -> CosmosWorkspaceResultRepository:
    client = CosmosClient.from_connection_string(
        config.connectionStrings.azCosmosDb,
        connection_verify=config.environment.lower() != "localhost",
    )
    return CosmosWorkspaceResultRepository(client, config.azCosmosDbDatabaseName)
