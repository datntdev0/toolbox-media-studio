"""Azure Cosmos DB implementation of the Scraping repository."""

from __future__ import annotations

import builtins
from datetime import UTC, datetime
from typing import Any, cast

from azure.core import MatchConditions
from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.config.app_config import AppConfig
from app.domain.scrapings import (
    Scraping,
    ScrapingCreateResult,
    ScrapingMetadata,
    ScrapingPage,
    ScrapingProgress,
    ScrapingStatus,
    ScrapingTask,
    ScrapingTaskStatus,
)
from app.repositories.scraping_repository import (
    ScrapingConflictError,
    ScrapingNotFoundError,
    ensure_scraping_size,
    reconciled_scraping_status,
)

SCRAPINGS_CONTAINER_NAME = "domain.scrapings"


class CosmosScrapingRepository:
    """Scraping repository backed by Cosmos DB."""

    def __init__(self, client: CosmosClient, database_name: str) -> None:
        self._database = client.create_database_if_not_exists(id=database_name)
        self._container = self._database.create_container_if_not_exists(
            id=SCRAPINGS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/createdBy"),
            unique_key_policy={"uniqueKeys": [{"paths": ["/activeKey"]}]},
        )

    def create_or_get_active(self, candidate: Scraping) -> ScrapingCreateResult:
        ensure_scraping_size(candidate)
        candidate.active_key = candidate.idempotency_key
        try:
            item = cast(
                dict[str, Any],
                self._container.create_item(body=self._serialize(candidate)),
            )
        except exceptions.CosmosHttpResponseError as exc:
            if getattr(exc, "status_code", None) != 409:
                raise
            existing = self._get_active(candidate.created_by, candidate.idempotency_key)
            if existing is None:
                raise
            return ScrapingCreateResult(scraping=existing, created=False)
        return ScrapingCreateResult(scraping=self._deserialize(item), created=True)

    def get(self, id: str, created_by: str | None = None) -> Scraping | None:
        if created_by is None:
            items = list(
                self._container.query_items(
                    query="SELECT TOP 1 * FROM c WHERE c.id = @id",
                    parameters=[{"name": "@id", "value": id}],
                    enable_cross_partition_query=True,
                )
            )
            return self._deserialize(items[0]) if items else None

        try:
            item = cast(
                dict[str, Any],
                self._container.read_item(item=id, partition_key=created_by),
            )
        except exceptions.CosmosResourceNotFoundError:
            return None
        return self._deserialize(item)

    def delete(self, id: str, created_by: str) -> None:
        try:
            self._container.delete_item(item=id, partition_key=created_by)
        except exceptions.CosmosResourceNotFoundError as exc:
            raise ScrapingNotFoundError from exc

    def list(
        self,
        created_by: str | None,
        limit: int,
        continuation_token: str | None,
        status: ScrapingStatus | None,
    ) -> ScrapingPage:
        query = "SELECT * FROM c"
        conditions: list[str] = []
        parameters: list[dict[str, object]] = []
        if created_by is not None:
            conditions.append("c.createdBy = @created_by")
            parameters.append({"name": "@created_by", "value": created_by})
        if status is not None:
            conditions.append("c.status = @status")
            parameters.append({"name": "@status", "value": status.value})
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY c.updatedAt DESC"

        if created_by is None:
            iterator = self._container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
                max_item_count=limit,
            )
        else:
            iterator = self._container.query_items(
                query=query,
                parameters=parameters,
                partition_key=created_by,
                max_item_count=limit,
            )
        page_iterator = iterator.by_page(continuation_token=continuation_token)
        page = list(next(page_iterator, []))
        return ScrapingPage(
            items=[self._deserialize(item) for item in page],
            continuation_token=cast(
                str | None,
                getattr(page_iterator, "continuation_token", None),
            ),
        )

    def set_status(
        self,
        id: str,
        created_by: str,
        status: ScrapingStatus,
        *,
        attempt: int | None = None,
        error: str | None = None,
        etag: str | None = None,
    ) -> Scraping:
        scraping = self._require(id, created_by)
        if scraping.status.is_terminal and status != scraping.status:
            raise ScrapingConflictError("Terminal Scrapings cannot change status")

        now = datetime.now(UTC)
        attempts = max(scraping.attempts, attempt or 0)
        operations: list[dict[str, object]] = [
            {"op": "replace", "path": "/status", "value": status.value},
            {"op": "replace", "path": "/attempts", "value": attempts},
            {"op": "replace", "path": "/lastError", "value": error},
            {"op": "replace", "path": "/updatedAt", "value": now.isoformat()},
        ]
        if status.is_terminal:
            operations.extend(
                [
                    {
                        "op": "replace",
                        "path": "/activeKey",
                        "value": f"terminal:{scraping.id}",
                    },
                    {
                        "op": "replace",
                        "path": "/completedAt",
                        "value": now.isoformat(),
                    },
                ]
            )
        return self._patch(
            scraping,
            operations,
            etag=etag or scraping.etag,
        )

    def update_task(
        self,
        id: str,
        created_by: str,
        task_id: str,
        status: ScrapingTaskStatus,
        *,
        attempts: int,
        error: str | None,
        result_available: bool,
        completed_at: datetime | None,
        etag: str | None = None,
    ) -> Scraping:
        scraping = self._require(id, created_by)
        index = next(
            (index for index, task in enumerate(scraping.tasks) if task.id == task_id),
            None,
        )
        if index is None:
            raise ScrapingNotFoundError

        task = scraping.tasks[index]
        task.status = status
        task.attempts = max(task.attempts, attempts)
        task.last_error = error
        task.result_available = result_available
        task.completed_at = completed_at
        scraping.progress = ScrapingProgress.from_tasks(scraping.tasks)
        now = datetime.now(UTC)

        return self._patch(
            scraping,
            [
                {
                    "op": "replace",
                    "path": f"/tasks/{index}",
                    "value": self._serialize_task(task),
                },
                {
                    "op": "replace",
                    "path": "/progress",
                    "value": self._serialize_progress(scraping.progress),
                },
                {"op": "replace", "path": "/updatedAt", "value": now.isoformat()},
            ],
            etag=etag or scraping.etag,
        )

    def reconcile(self, id: str, created_by: str, etag: str | None = None) -> Scraping:
        scraping = self._require(id, created_by)
        progress = ScrapingProgress.from_tasks(scraping.tasks)
        status = reconciled_scraping_status(progress)

        now = datetime.now(UTC)
        operations: list[dict[str, object]] = [
            {
                "op": "replace",
                "path": "/progress",
                "value": self._serialize_progress(progress),
            },
            {"op": "replace", "path": "/status", "value": status.value},
            {"op": "replace", "path": "/updatedAt", "value": now.isoformat()},
        ]
        if status.is_terminal:
            operations.extend(
                [
                    {
                        "op": "replace",
                        "path": "/activeKey",
                        "value": f"terminal:{scraping.id}",
                    },
                    {
                        "op": "replace",
                        "path": "/completedAt",
                        "value": now.isoformat(),
                    },
                ]
            )
        return self._patch(scraping, operations, etag=etag or scraping.etag)

    def list_stale_active(
        self,
        updated_before: datetime,
        limit: int,
    ) -> builtins.list[Scraping]:
        query = """
        SELECT TOP @limit * FROM c
        WHERE ARRAY_CONTAINS(@statuses, c.status)
        AND c.updatedAt < @updated_before
        ORDER BY c.updatedAt
        """
        items = self._container.query_items(
            query=query,
            parameters=[
                {"name": "@limit", "value": limit},
                {
                    "name": "@statuses",
                    "value": [
                        ScrapingStatus.QUEUED.value,
                        ScrapingStatus.PROCESSING.value,
                        ScrapingStatus.RETRYING.value,
                    ],
                },
                {"name": "@updated_before", "value": updated_before.isoformat()},
            ],
            enable_cross_partition_query=True,
        )
        return [self._deserialize(item) for item in items]

    def _get_active(self, created_by: str, idempotency_key: str) -> Scraping | None:
        query = """
        SELECT TOP 1 * FROM c
        WHERE c.createdBy = @created_by
        AND c.idempotencyKey = @idempotency_key
        AND ARRAY_CONTAINS(@statuses, c.status)
        """
        items = list(
            self._container.query_items(
                query=query,
                parameters=[
                    {"name": "@created_by", "value": created_by},
                    {"name": "@idempotency_key", "value": idempotency_key},
                    {
                        "name": "@statuses",
                        "value": [
                            ScrapingStatus.QUEUED.value,
                            ScrapingStatus.PROCESSING.value,
                            ScrapingStatus.RETRYING.value,
                        ],
                    },
                ],
                partition_key=created_by,
            )
        )
        return self._deserialize(items[0]) if items else None

    def _require(self, id: str, created_by: str) -> Scraping:
        scraping = self.get(id, created_by)
        if scraping is None:
            raise ScrapingNotFoundError
        return scraping

    def _patch(
        self,
        scraping: Scraping,
        operations: builtins.list[dict[str, object]],
        *,
        etag: str | None,
    ) -> Scraping:
        try:
            if etag is None:
                item = self._container.patch_item(
                    item=scraping.id,
                    partition_key=scraping.created_by,
                    patch_operations=operations,
                )
            else:
                item = self._container.patch_item(
                    item=scraping.id,
                    partition_key=scraping.created_by,
                    patch_operations=operations,
                    etag=etag,
                    match_condition=MatchConditions.IfNotModified,
                )
        except exceptions.CosmosAccessConditionFailedError as exc:
            raise ScrapingConflictError("Scraping has changed") from exc
        except exceptions.CosmosResourceNotFoundError as exc:
            raise ScrapingNotFoundError from exc
        return self._deserialize(item)

    @classmethod
    def _serialize(cls, scraping: Scraping) -> dict[str, Any]:
        return {
            "id": scraping.id,
            "crawlerId": scraping.crawler_id,
            "sourceUrl": scraping.source_url,
            "metadata": cls._serialize_metadata(scraping.metadata),
            "status": scraping.status.value,
            "tasks": [cls._serialize_task(task) for task in scraping.tasks],
            "progress": cls._serialize_progress(scraping.progress),
            "attempts": scraping.attempts,
            "lastError": scraping.last_error,
            "idempotencyKey": scraping.idempotency_key,
            "activeKey": scraping.active_key,
            "createdBy": scraping.created_by,
            "createdAt": scraping.created_at.isoformat(),
            "updatedAt": scraping.updated_at.isoformat(),
            "completedAt": (
                scraping.completed_at.isoformat() if scraping.completed_at is not None else None
            ),
        }

    @staticmethod
    def _serialize_metadata(metadata: ScrapingMetadata) -> dict[str, Any]:
        return {
            "sourceNovelId": metadata.source_novel_id,
            "title": metadata.title,
            "author": metadata.author,
            "category": metadata.category,
            "updatedDate": metadata.updated_date,
            "protagonists": metadata.protagonists,
            "description": metadata.description,
            "coverImageUrl": metadata.cover_image_url,
            "fetchedAt": metadata.fetched_at.isoformat(),
        }

    @staticmethod
    def _serialize_task(task: ScrapingTask) -> dict[str, Any]:
        return {
            "id": task.id,
            "sourceUrl": task.source_url,
            "title": task.title,
            "chapterNumber": task.chapter_number,
            "manifestIndex": task.manifest_index,
            "status": task.status.value,
            "attempts": task.attempts,
            "lastError": task.last_error,
            "resultAvailable": task.result_available,
            "completedAt": task.completed_at.isoformat() if task.completed_at else None,
        }

    @staticmethod
    def _serialize_progress(progress: ScrapingProgress) -> dict[str, int]:
        return {
            "total": progress.total,
            "pending": progress.pending,
            "processing": progress.processing,
            "retrying": progress.retrying,
            "completed": progress.completed,
            "failed": progress.failed,
        }

    @classmethod
    def _deserialize(cls, item: dict[str, Any]) -> Scraping:
        metadata = cast(dict[str, Any], item["metadata"])
        tasks = cast(list[dict[str, Any]], item.get("tasks", []))
        progress = cast(dict[str, Any], item["progress"])
        return Scraping(
            id=cast(str, item["id"]),
            crawler_id=cast(str, item["crawlerId"]),
            source_url=cast(str, item["sourceUrl"]),
            metadata=ScrapingMetadata(
                source_novel_id=cast(str, metadata["sourceNovelId"]),
                title=cast(str, metadata["title"]),
                author=cast(str | None, metadata.get("author")),
                category=cast(str | None, metadata.get("category")),
                updated_date=cast(str | None, metadata.get("updatedDate")),
                protagonists=list(cast(list[str], metadata.get("protagonists", []))),
                description=cast(str | None, metadata.get("description")),
                cover_image_url=cast(str | None, metadata.get("coverImageUrl")),
                fetched_at=datetime.fromisoformat(cast(str, metadata["fetchedAt"])),
            ),
            status=ScrapingStatus(cast(str, item["status"])),
            tasks=[
                ScrapingTask(
                    id=cast(str, task["id"]),
                    source_url=cast(str, task["sourceUrl"]),
                    title=cast(str, task["title"]),
                    chapter_number=cast(int | None, task.get("chapterNumber")),
                    manifest_index=cast(int, task["manifestIndex"]),
                    status=ScrapingTaskStatus(cast(str, task["status"])),
                    attempts=cast(int, task.get("attempts", 0)),
                    last_error=cast(str | None, task.get("lastError")),
                    result_available=cast(bool, task.get("resultAvailable", False)),
                    completed_at=_parse_optional_datetime(task.get("completedAt")),
                )
                for task in tasks
            ],
            progress=ScrapingProgress(
                total=cast(int, progress["total"]),
                pending=cast(int, progress["pending"]),
                processing=cast(int, progress.get("processing", 0)),
                retrying=cast(int, progress.get("retrying", 0)),
                completed=cast(int, progress.get("completed", 0)),
                failed=cast(int, progress.get("failed", 0)),
            ),
            attempts=cast(int, item.get("attempts", 0)),
            last_error=cast(str | None, item.get("lastError")),
            idempotency_key=cast(str, item["idempotencyKey"]),
            active_key=cast(str, item["activeKey"]),
            created_by=cast(str, item["createdBy"]),
            created_at=datetime.fromisoformat(cast(str, item["createdAt"])),
            updated_at=datetime.fromisoformat(cast(str, item["updatedAt"])),
            completed_at=_parse_optional_datetime(item.get("completedAt")),
            etag=cast(str | None, item.get("_etag")),
        )


def build_cosmos_scraping_repository(config: AppConfig) -> CosmosScrapingRepository:
    client = CosmosClient.from_connection_string(
        config.connectionStrings.azCosmosDb,
        connection_verify=config.environment.lower() != "localhost",
    )
    return CosmosScrapingRepository(client, config.azCosmosDbDatabaseName)


def _parse_optional_datetime(value: Any) -> datetime | None:
    return datetime.fromisoformat(value) if isinstance(value, str) else None
