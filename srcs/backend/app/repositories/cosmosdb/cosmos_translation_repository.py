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
    TranslationStatus,
)
from app.repositories.translation_repository import (
    TranslationConflictError,
    TranslationContinuationTokenError,
    TranslationNotFoundError,
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

    @staticmethod
    def _serialize(translation: Translation) -> dict[str, Any]:
        return {
            "id": translation.id,
            "name": translation.name,
            "novelId": translation.novel_id,
            "targetLanguage": translation.target_language,
            "configuration": _serialize_configuration(translation.configuration),
            "status": translation.status.value,
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
