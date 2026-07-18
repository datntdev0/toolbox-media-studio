from logging import Logger

from app.core.events.message_handler import MessageHandler, QueueMessage
from app.core.events.polling_queue_subscriber import PollingQueueSubscriber

SAMPLE_QUEUE_NAME = "sample"


class SampleHandler(MessageHandler):
    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def handle(self, message: QueueMessage) -> None:
        self._logger.info(
            "Received sample queue message",
            extra={"messageId": message.id, "content": dict(message.content or {})},
        )


class SampleQueueListener(PollingQueueSubscriber):
    def __init__(self, logger: Logger, workers: int = 1) -> None:
        super().__init__(
            name=SAMPLE_QUEUE_NAME,
            logger=logger,
            handler=SampleHandler(logger),
            workers=workers,
        )
