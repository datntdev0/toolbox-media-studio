"""Azure Storage Queue provider abstractions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol, cast

from azure.core.exceptions import ResourceExistsError
from azure.storage.queue import QueueClient

from app.core.azure import storage_api_version
from app.core.config import Settings

MAX_QUEUE_MESSAGE_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class SentQueueMessage:
    """Result returned after sending a queue message."""

    id: str | None


@dataclass(slots=True)
class ReceivedQueueMessage:
    """Queue message with the fields required for retry and delete."""

    id: str
    pop_receipt: str
    content: Mapping[str, Any]
    dequeue_count: int


class QueueProvider(Protocol):
    """Queue operations needed by services and consumers."""

    @property
    def queue_name(self) -> str: ...

    def ensure_exists(self) -> None: ...

    def send(self, message: Mapping[str, Any]) -> SentQueueMessage: ...

    def receive_one(self, visibility_timeout: int) -> ReceivedQueueMessage | None: ...

    def retry(self, message: ReceivedQueueMessage, visibility_timeout: int) -> None: ...

    def delete(self, message: ReceivedQueueMessage) -> None: ...


class QueueProviderFactory(Protocol):
    """Resolve a provider bound to one queue name."""

    def get(self, queue_name: str) -> QueueProvider: ...


class QueueMessageError(ValueError):
    """Raised when a queue message cannot be encoded or decoded safely."""


class AzureStorageQueueProvider:
    """Azure Storage Queue provider bound to a single queue."""

    def __init__(self, queue_client: QueueClient, queue_name: str) -> None:
        self._queue_client = queue_client
        self._queue_name = queue_name

    @property
    def queue_name(self) -> str:
        return self._queue_name

    def ensure_exists(self) -> None:
        try:
            self._queue_client.create_queue()
        except ResourceExistsError:
            return

    def send(self, message: Mapping[str, Any]) -> SentQueueMessage:
        content = self._encode(message)
        result = self._queue_client.send_message(content)
        return SentQueueMessage(id=cast(str | None, getattr(result, "id", None)))

    def receive_one(self, visibility_timeout: int) -> ReceivedQueueMessage | None:
        messages = list(
            self._queue_client.receive_messages(
                messages_per_page=1,
                visibility_timeout=visibility_timeout,
            )
        )
        if not messages:
            return None

        message = messages[0]
        if message.pop_receipt is None:
            raise QueueMessageError("Received queue message is missing a pop receipt")
        return ReceivedQueueMessage(
            id=message.id,
            pop_receipt=message.pop_receipt,
            content=self._decode(message.content),
            dequeue_count=cast(int, getattr(message, "dequeue_count", 1)),
        )

    def retry(self, message: ReceivedQueueMessage, visibility_timeout: int) -> None:
        result = self._queue_client.update_message(
            message.id,
            pop_receipt=message.pop_receipt,
            visibility_timeout=visibility_timeout,
        )
        new_pop_receipt = getattr(result, "pop_receipt", None)
        if isinstance(new_pop_receipt, str):
            message.pop_receipt = new_pop_receipt

    def delete(self, message: ReceivedQueueMessage) -> None:
        self._queue_client.delete_message(message.id, pop_receipt=message.pop_receipt)

    @staticmethod
    def _encode(message: Mapping[str, Any]) -> str:
        try:
            content = json.dumps(message, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except TypeError as exc:
            raise QueueMessageError("Queue message is not JSON serializable") from exc
        if len(content.encode("utf-8")) > MAX_QUEUE_MESSAGE_BYTES:
            raise QueueMessageError("Queue message exceeds the 64-KB Storage Queue limit")
        return content

    @staticmethod
    def _decode(content: str) -> Mapping[str, Any]:
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError as exc:
            raise QueueMessageError("Queue message content is not valid JSON") from exc
        if not isinstance(decoded, dict):
            raise QueueMessageError("Queue message content must be a JSON object")
        return cast(Mapping[str, Any], decoded)


class AzureStorageQueueProviderFactory:
    """Thread-safe Azure Queue provider factory cached by queue name."""

    def __init__(self, connection_string: str, api_version: str | None = None) -> None:
        self._connection_string = connection_string
        self._api_version = api_version
        self._providers: dict[str, AzureStorageQueueProvider] = {}
        self._lock = Lock()

    def get(self, queue_name: str) -> QueueProvider:
        with self._lock:
            provider = self._providers.get(queue_name)
            if provider is None:
                provider = AzureStorageQueueProvider(
                    queue_client=QueueClient.from_connection_string(
                        conn_str=self._connection_string,
                        queue_name=queue_name,
                        api_version=self._api_version,
                    ),
                    queue_name=queue_name,
                )
                self._providers[queue_name] = provider
            return provider


def build_azure_queue_provider_factory(settings: Settings) -> AzureStorageQueueProviderFactory:
    """Construct the default Azure Storage Queue provider factory."""

    return AzureStorageQueueProviderFactory(
        connection_string=settings.az_storage_queue_connection_string,
        api_version=storage_api_version(settings),
    )
