"""Azure Cosmos DB implementation of the novel chapter repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from azure.core import MatchConditions
from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.config.app_config import AppConfig
from app.domain.novels import NovelChapter, NovelChapterPage
from app.repositories.novel_chapter_repository import NovelChapterConflictError

NOVEL_CHAPTERS_CONTAINER_NAME = "domain.novel_chapters"


class CosmosNovelChapterRepository:
    """Chapter metadata and content stored in the novelId partition."""

    def __init__(self, client: CosmosClient, database_name: str) -> None:
        database = client.create_database_if_not_exists(id=database_name)
        self._container = database.create_container_if_not_exists(
            id=NOVEL_CHAPTERS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/novelId"),
        )

    def get(self, novel_id: str, chapter_id: str) -> NovelChapter | None:
        try:
            item = cast(
                dict[str, Any],
                self._container.read_item(item=chapter_id, partition_key=novel_id),
            )
        except exceptions.CosmosResourceNotFoundError:
            return None
        return self._deserialize(item)

    def get_by_id(self, chapter_id: str) -> NovelChapter | None:
        items = self._container.query_items(
            query="SELECT TOP 1 * FROM c WHERE c.id = @chapter_id",
            parameters=[{"name": "@chapter_id", "value": chapter_id}],
            enable_cross_partition_query=True,
        )
        item = next(iter(items), None)
        return self._deserialize(cast(dict[str, Any], item)) if item is not None else None

    def list(self, novel_id: str) -> NovelChapterPage:
        items = self._container.query_items(
            query=(
                "SELECT * FROM c WHERE c.novelId = @novel_id "
                "ORDER BY c.manifestIndex"
            ),
            parameters=[{"name": "@novel_id", "value": novel_id}],
            partition_key=novel_id,
        )
        return NovelChapterPage(items=[self._deserialize(item) for item in items])

    def save(
        self,
        chapter: NovelChapter,
        *,
        etag: str | None = None,
    ) -> NovelChapter:
        try:
            if etag is None:
                item = self._container.upsert_item(body=self._serialize(chapter))
            else:
                item = self._container.replace_item(
                    item=chapter.id,
                    body=self._serialize(chapter),
                    etag=etag,
                    match_condition=MatchConditions.IfNotModified,
                )
        except exceptions.CosmosAccessConditionFailedError as exc:
            raise NovelChapterConflictError("Novel chapter has changed") from exc
        except exceptions.CosmosResourceNotFoundError as exc:
            raise NovelChapterConflictError("Novel chapter has changed") from exc
        return self._deserialize(cast(dict[str, Any], item))

    def delete_by_novel(self, novel_id: str) -> None:
        chapter_ids = self._container.query_items(
            query="SELECT VALUE c.id FROM c WHERE c.novelId = @novel_id",
            parameters=[{"name": "@novel_id", "value": novel_id}],
            partition_key=novel_id,
        )
        for chapter_id in chapter_ids:
            try:
                self._container.delete_item(
                    item=cast(str, chapter_id),
                    partition_key=novel_id,
                )
            except exceptions.CosmosResourceNotFoundError:
                continue

    @staticmethod
    def _serialize(chapter: NovelChapter) -> dict[str, Any]:
        return {
            "id": chapter.id,
            "novelId": chapter.novel_id,
            "scrapingTaskId": chapter.scraping_task_id,
            "title": chapter.title,
            "chapterNumber": chapter.chapter_number,
            "manifestIndex": chapter.manifest_index,
            "sourceUrl": chapter.source_url,
            "content": chapter.content,
            "contentAvailable": chapter.content_available,
            "manuallyEdited": chapter.manually_edited,
            "sourceUpdated": chapter.source_updated,
            "sourceRemoved": chapter.source_removed,
            "sourceResultUpdatedAt": (
                chapter.source_result_updated_at.isoformat()
                if chapter.source_result_updated_at
                else None
            ),
            "createdAt": chapter.created_at.isoformat(),
            "updatedAt": chapter.updated_at.isoformat(),
            "updatedBy": chapter.updated_by,
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> NovelChapter:
        return NovelChapter(
            id=cast(str, item["id"]),
            novel_id=cast(str, item["novelId"]),
            scraping_task_id=cast(str, item["scrapingTaskId"]),
            title=cast(str, item["title"]),
            chapter_number=cast(int | None, item.get("chapterNumber")),
            manifest_index=cast(int, item["manifestIndex"]),
            source_url=cast(str, item.get("sourceUrl", "")),
            content=[
                cast(str, paragraph)
                for paragraph in cast(list[Any], item.get("content", []))
            ],
            content_available=cast(bool, item.get("contentAvailable", False)),
            manually_edited=cast(bool, item.get("manuallyEdited", False)),
            source_updated=cast(bool, item.get("sourceUpdated", False)),
            source_removed=cast(bool, item.get("sourceRemoved", False)),
            source_result_updated_at=_parse_datetime(item.get("sourceResultUpdatedAt")),
            created_at=datetime.fromisoformat(cast(str, item["createdAt"])),
            updated_at=datetime.fromisoformat(cast(str, item["updatedAt"])),
            updated_by=cast(str | None, item.get("updatedBy")),
            etag=cast(str | None, item.get("_etag")),
        )


def build_cosmos_novel_chapter_repository(
    config: AppConfig,
) -> CosmosNovelChapterRepository:
    client = CosmosClient.from_connection_string(
        config.connectionStrings.azCosmosDb,
        connection_verify=config.environment.lower() != "localhost",
    )
    return CosmosNovelChapterRepository(client, config.azCosmosDbDatabaseName)


def _parse_datetime(value: Any) -> datetime | None:
    return datetime.fromisoformat(value) if isinstance(value, str) else None
