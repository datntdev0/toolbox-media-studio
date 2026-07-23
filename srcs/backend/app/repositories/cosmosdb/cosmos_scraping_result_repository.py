"""Azure Cosmos DB implementation of the ScrapingResult repository."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.config.app_config import AppConfig
from app.domain.scraping_results import ScrapingResult
from app.repositories.scraping_repository import MAX_COSMOS_ITEM_BYTES, serialized_size
from app.repositories.scraping_result_repository import ScrapingResultTooLargeError

SCRAPING_RESULTS_CONTAINER_NAME = "scraping.results"


class CosmosScrapingResultRepository:
    """ScrapingResult repository backed by Cosmos DB."""

    def __init__(self, client: CosmosClient, database_name: str) -> None:
        self._database = client.create_database_if_not_exists(id=database_name)
        self._container = self._database.create_container_if_not_exists(
            id=SCRAPING_RESULTS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/scrapingId"),
        )

    def get(self, scraping_id: str, task_id: str) -> ScrapingResult | None:
        try:
            item = cast(
                dict[str, Any],
                self._container.read_item(item=task_id, partition_key=scraping_id),
            )
        except exceptions.CosmosResourceNotFoundError:
            return None
        return self._deserialize(item)

    def upsert(self, result: ScrapingResult) -> ScrapingResult:
        if result.id != result.task_id:
            raise ValueError("ScrapingResult id must equal taskId")
        if serialized_size(asdict(result)) > MAX_COSMOS_ITEM_BYTES:
            raise ScrapingResultTooLargeError("Scraping result is too large")
        item = cast(
            dict[str, Any],
            self._container.upsert_item(body=self._serialize(result)),
        )
        return self._deserialize(item)

    @staticmethod
    def _serialize(result: ScrapingResult) -> dict[str, Any]:
        return {
            "id": result.task_id,
            "scrapingId": result.scraping_id,
            "taskId": result.task_id,
            "title": result.title,
            "chapterNumber": result.chapter_number,
            "content": result.content,
            "createdAt": result.created_at.isoformat(),
            "updatedAt": result.updated_at.isoformat(),
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> ScrapingResult:
        return ScrapingResult(
            id=cast(str, item["id"]),
            scraping_id=cast(str, item["scrapingId"]),
            task_id=cast(str, item["taskId"]),
            title=cast(str, item["title"]),
            chapter_number=cast(int | None, item.get("chapterNumber")),
            content=list(cast(list[str], item.get("content", []))),
            created_at=datetime.fromisoformat(cast(str, item["createdAt"])),
            updated_at=datetime.fromisoformat(cast(str, item["updatedAt"])),
            etag=cast(str | None, item.get("_etag")),
        )


def build_cosmos_scraping_result_repository(
    config: AppConfig,
) -> CosmosScrapingResultRepository:
    client = CosmosClient.from_connection_string(
        config.connectionStrings.azCosmosDb,
        connection_verify=config.environment.lower() != "localhost",
    )
    return CosmosScrapingResultRepository(client, config.azCosmosDbDatabaseName)
