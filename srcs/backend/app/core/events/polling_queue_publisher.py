from collections.abc import Callable, Mapping
from typing import Any, Protocol

from app.core.config.app_config import AppConfig
from app.core.events.message_handler import QueueMessage
from app.core.events.polling_queue_client import AzureStorageQueueClient, PollingQueueClient

QueueClientFactory = Callable[[str], PollingQueueClient]


class PollingQueuePublisher(Protocol):
    def publish(
        self,
        queue_name: str,
        message: Mapping[str, Any],
    ) -> QueueMessage | None: ...


class AzureStorageQueuePublisher:
    def __init__(
        self,
        config: AppConfig | None = None,
        queue_client_factory: QueueClientFactory | None = None,
    ) -> None:
        self._config = config or AppConfig()
        self._queue_client_factory = queue_client_factory or self._create_queue_client

    def publish(self, queue_name: str, message: Mapping[str, Any]) -> QueueMessage:
        queue_client = self._queue_client_factory(queue_name)
        queue_client.ensure_exists()
        return queue_client.push(message)

    def _create_queue_client(self, queue_name: str) -> PollingQueueClient:
        return AzureStorageQueueClient(queue_name, self._config)
