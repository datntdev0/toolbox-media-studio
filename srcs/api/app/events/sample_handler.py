import time
from app.core.events.message_handler import MessageHandler
from app.core.events.polling_queue_client import QueueMessage
from app.core.events.polling_queue_listener import PollingQueueListener


class SampleHandler(MessageHandler):
    def handle(self, message: QueueMessage) -> None:
        # Implement your message processing logic here
        print(f"Handling message: {message.id} with content: {message.content}")
        time.sleep(30)  # Simulate some processing time

class SampleQueueListener(PollingQueueListener):
    def __init__(self, name: str, workers: int = 1) -> None:
        super().__init__(name, SampleHandler(), workers)


