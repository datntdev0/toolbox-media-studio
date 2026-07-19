import json
from collections.abc import Mapping
from typing import Any, Protocol

from azure.core.exceptions import ResourceExistsError
from azure.storage.queue import QueueClient

from app.core.config.app_config import AppConfig
from app.core.events.message_handler import QueueMessage


class PollingQueueClient(Protocol):
    @property
    def name(self) -> str: ...

    def ensure_exists(self) -> None: ...

    def pop(self) -> QueueMessage | None: ...

    def push(self, content: Mapping[str, Any]) -> QueueMessage: ...

    def delete(self, message: QueueMessage) -> None: ...


class AzureStorageQueueClient(PollingQueueClient):
    def __init__(self, name: str, config: AppConfig | None = None) -> None:
        settings = config or AppConfig()
        self._queue_client = QueueClient.from_connection_string(
            conn_str=settings.connectionStrings.azStorageQueue,
            api_version=_storage_api_version(settings),
            queue_name=name,
        )

    @property
    def name(self) -> str:
        return self._queue_client.queue_name

    def ensure_exists(self) -> None:
        try:
            self._queue_client.create_queue()
        except ResourceExistsError:
            pass

    def pop(self) -> QueueMessage | None:
        messages = list(self._queue_client.receive_messages(messages_per_page=1,visibility_timeout=1))
        message = messages[0] if messages else None
        if message is None:
            return None

        self._queue_client.delete_message(message.id, message.pop_receipt)
        content = json.loads(message.content)
        return QueueMessage(
            id=message.id,
            pop_receipt=message.pop_receipt,
            dequeue_count=message.dequeue_count,
            content=content,
        )

    def push(self, content: Mapping[str, Any]) -> QueueMessage:
        json_content = json.dumps(content)
        message = self._queue_client.send_message(json_content)
        return QueueMessage(id=message.id)


def _storage_api_version(settings: AppConfig) -> str | None:
    return "2024-11-04" if settings.environment.lower() == "localhost" else None
