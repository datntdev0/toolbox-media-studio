import json

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from azure.core.exceptions import ResourceExistsError
from azure.storage.queue import QueueClient

from app.core.config import get_settings

@dataclass()
class QueueMessage:
    id: str
    content: Mapping[str, Any] | None = None

class PollingQueueClient(Protocol):
    @property
    def name(self) -> str: ...

    def ensure_exists(self) -> None: ...

    def pop(self) -> QueueMessage | None: ...

    def push(self, content: Mapping[str, Any]) -> QueueMessage: ...

class AzureStorageQueueClient(PollingQueueClient):
    def __init__(self, name: str) -> None:
        self._queue_client = QueueClient.from_connection_string(
            conn_str=get_settings().az_storage_queue_connection_string,
            api_version=get_settings().az_storage_queue_api_version,
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
        messages = list(self._queue_client.receive_messages(messages_per_page=1))
        message = messages[0] if messages else None
        self._queue_client.delete_message(message) if message else None
        content = json.loads(message.content) if message else None
        return QueueMessage(id=message.id, content=content) if content else None

    def push(self, content: Mapping[str, Any]) -> QueueMessage:
        jsonContent = json.dumps(content)
        message = self._queue_client.send_message(jsonContent)
        return QueueMessage(id=message.id)
