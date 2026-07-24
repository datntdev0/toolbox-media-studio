"""Azure Cosmos DB implementation of the Scraping repository."""

from __future__ import annotations

import builtins
from copy import deepcopy
from datetime import datetime
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
    ScrapingQueueResult,
    ScrapingTask,
    ScrapingTaskStatus,
)
from app.repositories.scraping_repository import (
    ScrapingChapterRangeError,
    ScrapingConflictError,
    ScrapingNotFoundError,
    ensure_scraping_size,
    merge_scraping,
    touch_scraping,
)

SCRAPINGS_CONTAINER_NAME = "domain.scrapings"


class CosmosScrapingRepository:
    """Scraping repository backed by Azure Cosmos DB."""

    def __init__(self, client: CosmosClient, database_name: str) -> None:
        self._database = client.create_database_if_not_exists(id=database_name)
        self._container = self._database.create_container_if_not_exists(
            id=SCRAPINGS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/createdBy"),
            unique_key_policy={"uniqueKeys": [{"paths": ["/idempotencyKey"]}]},
        )

    def create_or_merge(self, candidate: Scraping) -> ScrapingCreateResult:
        ensure_scraping_size(candidate)
        try:
            item = cast(
                dict[str, Any],
                self._container.create_item(body=self._serialize(candidate)),
            )
            return ScrapingCreateResult(scraping=self._deserialize(item), created=True)
        except exceptions.CosmosHttpResponseError as exc:
            if getattr(exc, "status_code", None) != 409:
                raise

        existing = self._get_by_idempotency(
            candidate.created_by,
            candidate.idempotency_key,
        )
        if existing is None:
            raise ScrapingConflictError("Existing Scraping could not be loaded")
        for _ in range(3):
            merge_scraping(existing, candidate)
            ensure_scraping_size(existing)
            try:
                merged = self._replace(existing, etag=existing.etag)
                return ScrapingCreateResult(scraping=merged, created=False)
            except ScrapingConflictError:
                existing = self._get_by_idempotency(
                    candidate.created_by,
                    candidate.idempotency_key,
                )
                if existing is None:
                    raise ScrapingNotFoundError from None
        raise ScrapingConflictError("Scraping merge conflicted repeatedly")

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
    ) -> ScrapingPage:
        query = "SELECT * FROM c"
        parameters: list[dict[str, object]] = []
        if created_by is not None:
            query += " WHERE c.createdBy = @created_by"
            parameters.append({"name": "@created_by", "value": created_by})
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

    def queue_tasks(
        self,
        id: str,
        created_by: str,
        *,
        chapter_from: int,
        chapter_to: int,
        force: bool,
        etag: str | None = None,
    ) -> ScrapingQueueResult:
        scraping = self._require(id, created_by)
        self._check_etag(scraping, etag)
        matching = [
            task
            for task in scraping.tasks
            if task.chapter_number is not None
            and chapter_from <= task.chapter_number <= chapter_to
        ]
        if not matching:
            raise ScrapingChapterRangeError(
                "No scraping tasks match the requested chapter range"
            )
        queued = [
            task
            for task in matching
            if force
            or task.status
            not in {ScrapingTaskStatus.QUEUED, ScrapingTaskStatus.RUNNING}
        ]
        if not queued:
            return ScrapingQueueResult(scraping=scraping, tasks=[])

        queued_ids = {task.id for task in queued}
        for task in queued:
            task.status = ScrapingTaskStatus.QUEUED
            task.last_error = None
        touch_scraping(scraping)
        ensure_scraping_size(scraping)
        updated = self._replace(scraping, etag=etag or scraping.etag)
        return ScrapingQueueResult(
            scraping=updated,
            tasks=deepcopy([task for task in updated.tasks if task.id in queued_ids]),
        )

    def stop_queued_tasks(
        self,
        id: str,
        created_by: str,
        *,
        etag: str | None = None,
    ) -> Scraping:
        scraping = self._require(id, created_by)
        self._check_etag(scraping, etag)
        queued = [
            task
            for task in scraping.tasks
            if task.status == ScrapingTaskStatus.QUEUED
        ]
        if not queued:
            return scraping
        for task in queued:
            task.status = ScrapingTaskStatus.CREATED
        touch_scraping(scraping)
        ensure_scraping_size(scraping)
        return self._replace(scraping, etag=etag or scraping.etag)

    def claim_task(
        self,
        id: str,
        created_by: str,
        task_id: str,
        *,
        etag: str | None = None,
    ) -> Scraping | None:
        scraping = self._require(id, created_by)
        self._check_etag(scraping, etag)
        index = _task_index(scraping, task_id)
        task = scraping.tasks[index]
        if task.status != ScrapingTaskStatus.QUEUED:
            return None

        task.status = ScrapingTaskStatus.RUNNING
        task.attempts += 1
        task.last_error = None
        touch_scraping(scraping)
        return self._patch_task(scraping, index, etag=etag or scraping.etag)

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
        self._check_etag(scraping, etag)
        index = _task_index(scraping, task_id)
        task = scraping.tasks[index]
        task.status = status
        task.attempts = max(task.attempts, attempts)
        task.last_error = error
        task.result_available = result_available
        task.completed_at = completed_at
        touch_scraping(scraping)
        return self._patch_task(scraping, index, etag=etag or scraping.etag)

    def _patch_task(
        self,
        scraping: Scraping,
        index: int,
        *,
        etag: str | None,
    ) -> Scraping:
        return self._patch(
            scraping,
            [
                {
                    "op": "replace",
                    "path": f"/tasks/{index}",
                    "value": self._serialize_task(scraping.tasks[index]),
                },
                {
                    "op": "replace",
                    "path": "/progress",
                    "value": self._serialize_progress(scraping.progress),
                },
                {
                    "op": "replace",
                    "path": "/updatedAt",
                    "value": scraping.updated_at.isoformat(),
                },
            ],
            etag=etag,
        )

    def _get_by_idempotency(
        self,
        created_by: str,
        idempotency_key: str,
    ) -> Scraping | None:
        items = list(
            self._container.query_items(
                query=(
                    "SELECT TOP 1 * FROM c WHERE c.createdBy = @created_by "
                    "AND c.idempotencyKey = @idempotency_key"
                ),
                parameters=[
                    {"name": "@created_by", "value": created_by},
                    {"name": "@idempotency_key", "value": idempotency_key},
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

    @staticmethod
    def _check_etag(scraping: Scraping, etag: str | None) -> None:
        if etag is not None and scraping.etag != etag:
            raise ScrapingConflictError("Scraping has changed")

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
        return self._deserialize(cast(dict[str, Any], item))

    def _replace(self, scraping: Scraping, *, etag: str | None) -> Scraping:
        try:
            if etag is None:
                item = self._container.replace_item(
                    item=scraping.id,
                    body=self._serialize(scraping),
                )
            else:
                item = self._container.replace_item(
                    item=scraping.id,
                    body=self._serialize(scraping),
                    etag=etag,
                    match_condition=MatchConditions.IfNotModified,
                )
        except exceptions.CosmosAccessConditionFailedError as exc:
            raise ScrapingConflictError("Scraping has changed") from exc
        except exceptions.CosmosResourceNotFoundError as exc:
            raise ScrapingNotFoundError from exc
        return self._deserialize(cast(dict[str, Any], item))

    @classmethod
    def _serialize(cls, scraping: Scraping) -> dict[str, Any]:
        return {
            "id": scraping.id,
            "crawlerId": scraping.crawler_id,
            "sourceUrl": scraping.source_url,
            "metadata": cls._serialize_metadata(scraping.metadata),
            "tasks": [cls._serialize_task(task) for task in scraping.tasks],
            "progress": cls._serialize_progress(scraping.progress),
            "idempotencyKey": scraping.idempotency_key,
            "createdBy": scraping.created_by,
            "createdAt": scraping.created_at.isoformat(),
            "updatedAt": scraping.updated_at.isoformat(),
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
            "created": progress.created,
            "queued": progress.queued,
            "running": progress.running,
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
                created=cast(int, progress.get("created", 0)),
                queued=cast(int, progress.get("queued", 0)),
                running=cast(int, progress.get("running", 0)),
                completed=cast(int, progress.get("completed", 0)),
                failed=cast(int, progress.get("failed", 0)),
            ),
            idempotency_key=cast(str, item["idempotencyKey"]),
            created_by=cast(str, item["createdBy"]),
            created_at=datetime.fromisoformat(cast(str, item["createdAt"])),
            updated_at=datetime.fromisoformat(cast(str, item["updatedAt"])),
            etag=cast(str | None, item.get("_etag")),
        )


def build_cosmos_scraping_repository(config: AppConfig) -> CosmosScrapingRepository:
    client = CosmosClient.from_connection_string(
        config.connectionStrings.azCosmosDb,
        connection_verify=config.environment.lower() != "localhost",
    )
    return CosmosScrapingRepository(client, config.azCosmosDbDatabaseName)


def _task_index(scraping: Scraping, task_id: str) -> int:
    index = next(
        (index for index, task in enumerate(scraping.tasks) if task.id == task_id),
        None,
    )
    if index is None:
        raise ScrapingNotFoundError
    return index


def _parse_optional_datetime(value: Any) -> datetime | None:
    return datetime.fromisoformat(value) if isinstance(value, str) else None
