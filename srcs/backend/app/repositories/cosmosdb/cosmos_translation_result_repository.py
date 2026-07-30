"""Azure Cosmos DB implementation of translation results."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.config.app_config import AppConfig
from app.domain.translation_results import TranslationResult
from app.repositories.scraping_repository import MAX_COSMOS_ITEM_BYTES, serialized_size
from app.repositories.translation_result_repository import TranslationResultTooLargeError

TRANSLATION_RESULTS_CONTAINER_NAME = "domain.translation_results"


class CosmosTranslationResultRepository:
    """TranslationResult repository partitioned by translation ID."""

    def __init__(self, client: CosmosClient, database_name: str) -> None:
        database = client.create_database_if_not_exists(id=database_name)
        self._container = database.create_container_if_not_exists(
            id=TRANSLATION_RESULTS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/translationId"),
        )

    def get(self, translation_id: str, task_id: str) -> TranslationResult | None:
        try:
            item = cast(
                dict[str, Any],
                self._container.read_item(item=task_id, partition_key=translation_id),
            )
        except exceptions.CosmosResourceNotFoundError:
            return None
        return self._deserialize(item)

    def list_by_translation(self, translation_id: str) -> list[TranslationResult]:
        items = self._container.query_items(
            query="SELECT * FROM c WHERE c.translationId = @translation_id",
            parameters=[
                {"name": "@translation_id", "value": translation_id},
            ],
            partition_key=translation_id,
        )
        return [self._deserialize(item) for item in items]

    def upsert(self, result: TranslationResult) -> TranslationResult:
        if result.id != result.task_id:
            raise ValueError("TranslationResult id must equal taskId")
        if serialized_size(asdict(result)) > MAX_COSMOS_ITEM_BYTES:
            raise TranslationResultTooLargeError("Translation result is too large")
        item = cast(
            dict[str, Any],
            self._container.upsert_item(body=self._serialize(result)),
        )
        return self._deserialize(item)

    def delete_by_translation(self, translation_id: str) -> None:
        task_ids = list(
            self._container.query_items(
                query="SELECT VALUE c.id FROM c WHERE c.translationId = @translation_id",
                parameters=[
                    {"name": "@translation_id", "value": translation_id},
                ],
                partition_key=translation_id,
            )
        )
        for task_id in task_ids:
            try:
                self._container.delete_item(
                    item=cast(str, task_id),
                    partition_key=translation_id,
                )
            except exceptions.CosmosResourceNotFoundError:
                continue

    @staticmethod
    def _serialize(result: TranslationResult) -> dict[str, Any]:
        return {
            "id": result.task_id,
            "translationId": result.translation_id,
            "taskId": result.task_id,
            "title": result.title,
            "chapterNumber": result.chapter_number,
            "content": result.content,
            "createdAt": result.created_at.isoformat(),
            "updatedAt": result.updated_at.isoformat(),
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> TranslationResult:
        return TranslationResult(
            id=cast(str, item["id"]),
            translation_id=cast(str, item["translationId"]),
            task_id=cast(str, item["taskId"]),
            title=cast(str, item["title"]),
            chapter_number=cast(int | None, item.get("chapterNumber")),
            content=list(cast(list[str], item.get("content", []))),
            created_at=datetime.fromisoformat(cast(str, item["createdAt"])),
            updated_at=datetime.fromisoformat(cast(str, item["updatedAt"])),
            etag=cast(str | None, item.get("_etag")),
        )


def build_cosmos_translation_result_repository(
    config: AppConfig,
) -> CosmosTranslationResultRepository:
    client = CosmosClient.from_connection_string(
        config.connectionStrings.azCosmosDb,
        connection_verify=config.environment.lower() != "localhost",
    )
    return CosmosTranslationResultRepository(client, config.azCosmosDbDatabaseName)
