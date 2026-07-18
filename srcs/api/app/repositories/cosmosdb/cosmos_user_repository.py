from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from azure.core import MatchConditions
from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.config.app_config import AppConfig
from app.domain.users import User, UserPage, UserRole, UserStatus
from app.repositories.user_repository import (
    UserAlreadyExistsError,
    UserConflictError,
    UserNotFoundError,
)

USERS_CONTAINER_NAME = "sys.users"


class CosmosUserRepository:
    """User repository backed by Azure Cosmos DB."""

    def __init__(self, client: CosmosClient, dbName: str) -> None:
        self._database = client.create_database_if_not_exists(id=dbName)
        self._container = self._database.create_container_if_not_exists(
            id=USERS_CONTAINER_NAME,
            partition_key=PartitionKey(path="/id"),
        )

    def create(self, user: User) -> User:
        if self.get_by_email(user.email) is not None:
            raise UserAlreadyExistsError

        try:
            item = cast(dict[str, Any], self._container.create_item(body=self._serialize(user)))
        except exceptions.CosmosResourceExistsError as exc:
            raise UserAlreadyExistsError from exc
        return self._deserialize(item)

    def get_by_id(self, id: str) -> User | None:
        try:
            item = cast(
                dict[str, Any],
                self._container.read_item(item=id, partition_key=id),
            )
        except exceptions.CosmosResourceNotFoundError:
            raise UserNotFoundError
        user = self._deserialize(item)
        if user.status == UserStatus.DELETED:
            return None
        return user

    def get_by_email(self, email: str) -> User | None:
        normalized_email = email.strip().lower()
        query = """
        SELECT TOP 1 * FROM c
        WHERE c.normalizedEmail = @normalized_email
        """
        items = list(
            self._container.query_items(
                query=query,
                parameters=[{"name": "@normalized_email", "value": normalized_email}],
                enable_cross_partition_query=True,
            )
        )
        if not items:
            return None
        user = self._deserialize(items[0])
        if user.status == UserStatus.DELETED:
            return None
        return user

    def list(self, limit: int, continuation_token: str | None) -> UserPage:
        query = """
        SELECT * FROM c
        WHERE c.status != @deleted_status
        ORDER BY c.createdAt
        """
        iterator = self._container.query_items(
            query=query,
            parameters=[{"name": "@deleted_status", "value": UserStatus.DELETED.value}],
            enable_cross_partition_query=True,
            max_item_count=limit,
        )
        page_iterator = iterator.by_page(continuation_token=continuation_token)
        page: list[dict[str, Any]] = list(next(page_iterator, []))
        items = [self._deserialize(item) for item in page]
        return UserPage(items=items, continuation_token=None)

    def update(self, user: User, etag: str | None) -> User:
        existing = self.get_by_id(user.id)
        if existing is None:
            raise UserNotFoundError
        if (
            existing.normalized_email != user.normalized_email
            and self.get_by_email(user.email) is not None
        ):
            raise UserAlreadyExistsError

        serialized = self._serialize(user)
        options: dict[str, Any] = {}
        if etag is not None:
            options["etag"] = etag
            options["match_condition"] = MatchConditions.IfNotModified

        try:
            item = cast(
                dict[str, Any],
                self._container.replace_item(item=user.id, body=serialized, **options),
            )
        except exceptions.CosmosAccessConditionFailedError as exc:
            raise UserConflictError from exc
        except exceptions.CosmosResourceNotFoundError as exc:
            raise UserNotFoundError from exc

        return self._deserialize(item)

    def delete(self, id: str, etag: str | None, deleted_by: str) -> None:
        user = self.get_by_id(id)
        if user is None:
            raise UserNotFoundError

        now = datetime.now(UTC)
        user.status = UserStatus.DELETED
        user.deleted_at = now
        user.deleted_by = deleted_by
        user.updated_at = now
        user.updated_by = deleted_by
        self.update(user, etag)

    @staticmethod
    def _serialize(user: User) -> dict[str, Any]:
        return {
            "id": user.id,
            "email": user.email,
            "normalizedEmail": user.normalized_email,
            "passwordHash": user.password_hash,
            "displayName": user.display_name,
            "role": user.role.value,
            "status": user.status.value,
            "createdBy": user.created_by,
            "createdAt": user.created_at.isoformat(),
            "updatedBy": user.updated_by,
            "updatedAt": user.updated_at.isoformat(),
            "deletedAt": user.deleted_at.isoformat() if user.deleted_at else None,
            "deletedBy": user.deleted_by,
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> User:
        return User(
            id=cast(str, item["id"]),
            email=cast(str, item["email"]),
            normalized_email=cast(str, item["normalizedEmail"]),
            password_hash=cast(str, item["passwordHash"]),
            display_name=cast(str | None, item.get("displayName")),
            role=UserRole(cast(str, item["role"])),
            status=UserStatus(cast(str, item["status"])),
            created_by=cast(str, item["createdBy"]),
            created_at=datetime.fromisoformat(cast(str, item["createdAt"])),
            updated_by=cast(str, item["updatedBy"]),
            updated_at=datetime.fromisoformat(cast(str, item["updatedAt"])),
            deleted_at=_parse_optional_datetime(item.get("deletedAt")),
            deleted_by=cast(str | None, item.get("deletedBy")),
            etag=cast(str | None, item.get("_etag")),
        )


def build_cosmos_user_repository(settings: AppConfig) -> CosmosUserRepository:
    """Construct the default Cosmos-backed repository."""

    client = CosmosClient.from_connection_string(
        settings.connectionStrings.azCosmosDb,
        connection_verify=True,
    )
    return CosmosUserRepository(client=client, dbName=settings.azCosmosDbDatabaseName)


def _parse_optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(cast(str, value))
