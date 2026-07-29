"""Azure Cosmos DB implementation of the translation repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from azure.core import MatchConditions
from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.config.app_config import AppConfig
from app.domain.translations import (
    Translation,
    TranslationConfiguration,
    TranslationPage,
    TranslationProgress,
    TranslationQueueResult,
    TranslationStatus,
    TranslationTask,
    TranslationTaskStatus,
)
from app.repositories.translation_repository import (
    TranslationChapterRangeError,
    TranslationConflictError,
    TranslationContinuationTokenError,
    TranslationNotFoundError,
    reconcile_translation_status,
)

TRANSLATIONS_CONTAINER_NAME = "domain.translations"


class CosmosTranslationRepository:
    """Translation repository partitioned by translation identifier."""

    def __init__(self, client: CosmosClient, database_name: str) -> None:
        database = client.create_database_if_not_exists(id=database_name)
        self._container = database.create_container_if_not_exists(
            id=TRANSLATIONS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/id"),
        )

    def create(self, translation: Translation) -> Translation:
        item = cast(
            dict[str, Any],
            self._container.create_item(body=self._serialize(translation)),
        )
        return self._deserialize(item)

    def get_by_id(self, id: str) -> Translation | None:
        try:
            item = cast(
                dict[str, Any],
                self._container.read_item(item=id, partition_key=id),
            )
        except exceptions.CosmosResourceNotFoundError:
            return None
        translation = self._deserialize(item)
        if translation.status == TranslationStatus.DELETED:
            return None
        return translation

    def list(self, limit: int, continuation_token: str | None) -> TranslationPage:
        query = (
            "SELECT * FROM c WHERE c.status != @deleted_status "
            "ORDER BY c.updatedAt DESC"
        )
        iterator = self._container.query_items(
            query=query,
            parameters=[
                {"name": "@deleted_status", "value": TranslationStatus.DELETED.value}
            ],
            max_item_count=limit,
            enable_cross_partition_query=True,
        )
        page_iterator: Any = iterator.by_page(continuation_token=continuation_token)
        try:
            page = list(next(page_iterator, []))
        except exceptions.CosmosHttpResponseError as exc:
            if exc.status_code == 400:
                raise TranslationContinuationTokenError(
                    "Invalid continuation token"
                ) from exc
            raise
        return TranslationPage(
            items=[self._deserialize(item) for item in page],
            continuation_token=cast(str | None, page_iterator.continuation_token),
        )

    def update(self, translation: Translation, etag: str | None) -> Translation:
        if self.get_by_id(translation.id) is None:
            raise TranslationNotFoundError

        options: dict[str, Any] = {}
        if etag is not None:
            options["etag"] = etag
            options["match_condition"] = MatchConditions.IfNotModified
        try:
            item = cast(
                dict[str, Any],
                self._container.replace_item(
                    item=translation.id,
                    body=self._serialize(translation),
                    **options,
                ),
            )
        except exceptions.CosmosAccessConditionFailedError as exc:
            raise TranslationConflictError("Translation has changed") from exc
        except exceptions.CosmosResourceNotFoundError as exc:
            raise TranslationNotFoundError from exc
        return self._deserialize(item)

    def delete(self, id: str, etag: str | None, deleted_by: str) -> None:
        translation = self.get_by_id(id)
        if translation is None:
            raise TranslationNotFoundError

        now = datetime.now(UTC)
        translation.status = TranslationStatus.DELETED
        translation.deleted_at = now
        translation.deleted_by = deleted_by
        translation.updated_at = now
        translation.updated_by = deleted_by
        self.update(translation, etag)

    def queue_tasks(
        self,
        id: str,
        *,
        chapter_index_from: int,
        chapter_index_to: int,
        force: bool,
        etag: str | None,
    ) -> TranslationQueueResult:
        translation = self._require(id)
        self._check_etag(translation, etag)
        matching = [
            task
            for task in translation.tasks
            if not task.source_removed
            and chapter_index_from <= task.manifest_index + 1 <= chapter_index_to
        ]
        if not matching:
            raise TranslationChapterRangeError(
                "No translation tasks match the requested chapter index range"
            )
        queued = [
            task
            for task in matching
            if force
            or task.status
            not in {TranslationTaskStatus.QUEUED, TranslationTaskStatus.RUNNING}
        ]
        if not queued:
            return TranslationQueueResult(translation=translation, tasks=[])
        queued_ids = {task.id for task in queued}
        for task in queued:
            task.status = TranslationTaskStatus.QUEUED
            task.last_error = None
        translation.status = TranslationStatus.RUNNING
        self._touch(translation)
        updated = self.update(translation, etag or translation.etag)
        return TranslationQueueResult(
            translation=updated,
            tasks=[task for task in updated.tasks if task.id in queued_ids],
        )

    def stop_queued_tasks(self, id: str, *, etag: str | None) -> Translation:
        translation = self._require(id)
        self._check_etag(translation, etag)
        for task in translation.tasks:
            if task.status == TranslationTaskStatus.QUEUED:
                task.status = TranslationTaskStatus.CREATED
        translation.progress = TranslationProgress.from_tasks(translation.tasks)
        translation.status = TranslationStatus.STOPPED
        translation.updated_at = datetime.now(UTC)
        return self.update(translation, etag or translation.etag)

    def claim_task(
        self,
        id: str,
        task_id: str,
        *,
        etag: str | None,
    ) -> Translation | None:
        translation = self._require(id)
        self._check_etag(translation, etag)
        task = self._require_task(translation, task_id)
        if (
            translation.status == TranslationStatus.STOPPED
            or task.source_removed
            or task.status != TranslationTaskStatus.QUEUED
        ):
            return None
        task.status = TranslationTaskStatus.RUNNING
        task.attempts += 1
        task.last_error = None
        self._touch(translation)
        return self.update(translation, etag or translation.etag)

    def update_task(
        self,
        id: str,
        task_id: str,
        status: TranslationTaskStatus,
        *,
        attempts: int,
        error: str | None,
        result_available: bool,
        completed_at: datetime | None,
        source_chapter_updated_at: datetime | None,
        clear_source_updated: bool,
        etag: str | None,
    ) -> Translation:
        translation = self._require(id)
        self._check_etag(translation, etag)
        task = self._require_task(translation, task_id)
        task.status = status
        task.attempts = max(task.attempts, attempts)
        task.last_error = error
        task.result_available = result_available
        task.completed_at = completed_at
        if source_chapter_updated_at is not None:
            task.source_chapter_updated_at = source_chapter_updated_at
        if clear_source_updated:
            task.source_updated = False
        self._touch(translation)
        return self.update(translation, etag or translation.etag)

    def _require(self, id: str) -> Translation:
        translation = self.get_by_id(id)
        if translation is None:
            raise TranslationNotFoundError
        return translation

    @staticmethod
    def _require_task(translation: Translation, task_id: str) -> TranslationTask:
        task = next((item for item in translation.tasks if item.id == task_id), None)
        if task is None:
            raise TranslationNotFoundError
        return task

    @staticmethod
    def _check_etag(translation: Translation, etag: str | None) -> None:
        if etag is not None and translation.etag != etag:
            raise TranslationConflictError("Translation has changed")

    @staticmethod
    def _touch(translation: Translation) -> None:
        translation.progress = TranslationProgress.from_tasks(translation.tasks)
        translation.updated_at = datetime.now(UTC)
        translation.status = reconcile_translation_status(translation)

    @staticmethod
    def _serialize(translation: Translation) -> dict[str, Any]:
        return {
            "id": translation.id,
            "name": translation.name,
            "novelId": translation.novel_id,
            "targetLanguage": translation.target_language,
            "configuration": _serialize_configuration(translation.configuration),
            "status": translation.status.value,
            "tasks": [_serialize_task(task) for task in translation.tasks],
            "progress": _serialize_progress(translation.progress),
            "createdBy": translation.created_by,
            "createdAt": translation.created_at.isoformat(),
            "updatedBy": translation.updated_by,
            "updatedAt": translation.updated_at.isoformat(),
            "deletedAt": (
                translation.deleted_at.isoformat() if translation.deleted_at else None
            ),
            "deletedBy": translation.deleted_by,
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> Translation:
        return Translation(
            id=cast(str, item["id"]),
            name=cast(str, item["name"]),
            novel_id=cast(str, item["novelId"]),
            target_language=cast(str, item["targetLanguage"]),
            configuration=_deserialize_configuration(item.get("configuration")),
            status=TranslationStatus(cast(str, item["status"])),
            created_by=cast(str, item["createdBy"]),
            created_at=datetime.fromisoformat(cast(str, item["createdAt"])),
            updated_by=cast(str, item["updatedBy"]),
            updated_at=datetime.fromisoformat(cast(str, item["updatedAt"])),
            tasks=[
                _deserialize_task(task)
                for task in cast(list[dict[str, Any]], item.get("tasks", []))
            ],
            progress=_deserialize_progress(item.get("progress")),
            deleted_at=_optional_datetime(item.get("deletedAt")),
            deleted_by=cast(str | None, item.get("deletedBy")),
            etag=cast(str | None, item.get("_etag")),
        )


def build_cosmos_translation_repository(config: AppConfig) -> CosmosTranslationRepository:
    """Construct the default Cosmos-backed translation repository."""

    client = CosmosClient.from_connection_string(
        config.connectionStrings.azCosmosDb,
        connection_verify=True,
    )
    return CosmosTranslationRepository(client, config.azCosmosDbDatabaseName)


def _serialize_configuration(
    configuration: TranslationConfiguration | None,
) -> dict[str, str] | None:
    if configuration is None:
        return None
    return {
        "providerId": configuration.provider_id,
        "modelId": configuration.model_id,
        "globalPrompt": configuration.global_prompt,
    }


def _deserialize_configuration(value: Any) -> TranslationConfiguration | None:
    if value is None:
        return None
    configuration = cast(dict[str, Any], value)
    return TranslationConfiguration(
        provider_id=cast(str, configuration["providerId"]),
        model_id=cast(str, configuration["modelId"]),
        global_prompt=cast(str, configuration["globalPrompt"]),
    )


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(cast(str, value))


def _serialize_task(task: TranslationTask) -> dict[str, Any]:
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
    }


def _deserialize_task(item: dict[str, Any]) -> TranslationTask:
    return TranslationTask(
        id=cast(str, item["id"]),
        title=cast(str, item["title"]),
        chapter_number=cast(int | None, item.get("chapterNumber")),
        manifest_index=cast(int, item["manifestIndex"]),
        source_chapter_updated_at=datetime.fromisoformat(
            cast(str, item["sourceChapterUpdatedAt"])
        ),
        status=TranslationTaskStatus(
            cast(str, item.get("status", TranslationTaskStatus.CREATED.value))
        ),
        attempts=cast(int, item.get("attempts", 0)),
        last_error=cast(str | None, item.get("lastError")),
        result_available=cast(bool, item.get("resultAvailable", False)),
        completed_at=_optional_datetime(item.get("completedAt")),
        source_updated=cast(bool, item.get("sourceUpdated", False)),
        source_removed=cast(bool, item.get("sourceRemoved", False)),
    )


def _serialize_progress(progress: TranslationProgress) -> dict[str, int]:
    return {
        "total": progress.total,
        "created": progress.created,
        "queued": progress.queued,
        "running": progress.running,
        "completed": progress.completed,
        "failed": progress.failed,
    }


def _deserialize_progress(value: Any) -> TranslationProgress:
    if not isinstance(value, dict):
        return TranslationProgress()
    return TranslationProgress(
        total=int(value.get("total", 0)),
        created=int(value.get("created", 0)),
        queued=int(value.get("queued", 0)),
        running=int(value.get("running", 0)),
        completed=int(value.get("completed", 0)),
        failed=int(value.get("failed", 0)),
    )
