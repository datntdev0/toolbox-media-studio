from typing import Protocol

from app.core.events.polling_queue_client import QueueMessage

class MessageHandler(Protocol):
    def handle(self, message: QueueMessage) -> None: ...