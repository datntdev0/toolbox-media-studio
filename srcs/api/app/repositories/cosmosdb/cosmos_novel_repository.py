"""Azure Cosmos DB implementation of the novel repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from azure.core import MatchConditions
from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.config import Settings
from app.core.startup import _should_verify_connection
from app.domain.novels import Novel, NovelPage, NovelStatus
from app.repositories.novel_repository import NovelConflictError, NovelNotFoundError

NOVELS_CONTAINER_NAME = "novels"


class CosmosNovelRepository:
    """Novel repository backed by Azure Cosmos DB."""

    def __init__(self, client: CosmosClient, settings: Settings) -> None:
        self._database = client.create_database_if_not_exists(id=settings.az_cosmosdb_database_name)
        self._container = self._database.create_container_if_not_exists(
            id=NOVELS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/createdBy"),
        )

    def create(self, novel: Novel) -> Novel:
        item = cast(dict[str, Any], self._container.create_item(body=self._serialize(novel)))
        return self._deserialize(item)

    def get_by_id(self, id: str, created_by: str) -> Novel | None:
        try:
            item = cast(
                dict[str, Any],
                self._container.read_item(item=id, partition_key=created_by),
            )
        except exceptions.CosmosResourceNotFoundError:
            return None
        novel = self._deserialize(item)
        if novel.status == NovelStatus.DELETED:
            return None
        return novel

    def list(self, created_by: str, limit: int, continuation_token: str | None) -> NovelPage:
        query = """
        SELECT * FROM c
        WHERE c.createdBy = @created_by AND c.status != @deleted_status
        ORDER BY c.createdAt
        """
        iterator = self._container.query_items(
            query=query,
            parameters=[
                {"name": "@created_by", "value": created_by},
                {"name": "@deleted_status", "value": NovelStatus.DELETED.value},
            ],
            partition_key=created_by,
            max_item_count=limit,
        )
        page_iterator = iterator.by_page(continuation_token=continuation_token)
        page: list[dict[str, Any]] = list(next(page_iterator, []))
        items = [self._deserialize(item) for item in page]
        return NovelPage(items=items, continuation_token=None)

    def update(self, novel: Novel, etag: str | None) -> Novel:
        existing = self.get_by_id(novel.id, novel.created_by)
        if existing is None:
            raise NovelNotFoundError

        serialized = self._serialize(novel)
        options: dict[str, Any] = {}
        if etag is not None:
            options["etag"] = etag
            options["match_condition"] = MatchConditions.IfNotModified

        try:
            item = cast(
                dict[str, Any],
                self._container.replace_item(item=novel.id, body=serialized, **options),
            )
        except exceptions.CosmosAccessConditionFailedError as exc:
            raise NovelConflictError from exc
        except exceptions.CosmosResourceNotFoundError as exc:
            raise NovelNotFoundError from exc

        return self._deserialize(item)

    def delete(self, id: str, created_by: str, etag: str | None, deleted_by: str) -> None:
        novel = self.get_by_id(id, created_by)
        if novel is None:
            raise NovelNotFoundError

        now = datetime.now(UTC)
        novel.status = NovelStatus.DELETED
        novel.deleted_at = now
        novel.deleted_by = deleted_by
        novel.updated_at = now
        novel.updated_by = deleted_by
        self.update(novel, etag)

    @staticmethod
    def _serialize(novel: Novel) -> dict[str, Any]:
        return {
            "id": novel.id,
            "title": novel.title,
            "description": novel.description,
            "coverImageUrl": novel.cover_image_url,
            "language": novel.language,
            "author": novel.author,
            "tags": novel.tags,
            "notes": novel.notes,
            "status": novel.status.value,
            "createdBy": novel.created_by,
            "createdAt": novel.created_at.isoformat(),
            "updatedBy": novel.updated_by,
            "updatedAt": novel.updated_at.isoformat(),
            "deletedAt": novel.deleted_at.isoformat() if novel.deleted_at else None,
            "deletedBy": novel.deleted_by,
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> Novel:
        return Novel(
            id=cast(str, item["id"]),
            title=cast(str, item["title"]),
            description=cast(str | None, item.get("description")),
            cover_image_url=cast(str | None, item.get("coverImageUrl")),
            language=cast(str | None, item.get("language")),
            author=cast(str | None, item.get("author")),
            tags=list(cast(list[str], item.get("tags", []))),
            notes=cast(str | None, item.get("notes")),
            status=NovelStatus(cast(str, item["status"])),
            created_by=cast(str, item["createdBy"]),
            created_at=datetime.fromisoformat(cast(str, item["createdAt"])),
            updated_by=cast(str, item["updatedBy"]),
            updated_at=datetime.fromisoformat(cast(str, item["updatedAt"])),
            deleted_at=_parse_optional_datetime(item.get("deletedAt")),
            deleted_by=cast(str | None, item.get("deletedBy")),
            etag=cast(str | None, item.get("_etag")),
        )


def build_cosmos_novel_repository(settings: Settings) -> CosmosNovelRepository:
    """Construct the default Cosmos-backed repository."""

    client = CosmosClient.from_connection_string(
        settings.az_cosmosdb_connection_string,
        connection_verify=_should_verify_connection(settings),
    )
    return CosmosNovelRepository(client=client, settings=settings)


def _parse_optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(cast(str, value))
