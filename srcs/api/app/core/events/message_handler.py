from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class QueueMessage:
    id: str
    pop_receipt: str | None = None
    dequeue_count: int = 1
    content: Mapping[str, Any] | None = None


class MessageHandler(Protocol):
    def handle(self, message: QueueMessage) -> None: ...