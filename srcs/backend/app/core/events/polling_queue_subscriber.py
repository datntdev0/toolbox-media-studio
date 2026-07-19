import datetime
import time
from collections.abc import Callable
from logging import Logger
from threading import Event

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config.app_config import AppConfig
from app.core.events.message_handler import MessageHandler
from app.core.events.polling_queue_client import AzureStorageQueueClient, PollingQueueClient

LISTENER_SEEK_INTERVAL_SECONDS = 5
QueueClientFactory = Callable[[str], PollingQueueClient]

class PollingQueueSubscriber:
    def __init__(
        self,
        name: str,
        logger: Logger,
        handler: MessageHandler,
        workers: int = 1,
        config: AppConfig | None = None,
        queue_client_factory: QueueClientFactory | None = None,
    ) -> None:
        self._name = name
        self._logger = logger
        self._workers = workers
        self._handler = handler
        self._stop_event = Event()
        self._config = config or AppConfig()
        self._queue_client_factory = queue_client_factory or self._create_queue_client
        self._queue_client = self._queue_client_factory(name)
        self._scheduler = BackgroundScheduler(
            executors={"default": ThreadPoolExecutor(max_workers=workers)},
            job_defaults={"coalesce": True, "max_instances": workers},
        )

    def start(self) -> None:
        self._queue_client.ensure_exists()
        for i in range(self._workers):
            self._add_worker(i)
        self._logger.info(
            "Starting queue listener for '%s' with %d workers",
            self._name,
            self._workers,
        )
        self._scheduler.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
    
    def _add_worker(self, index: int) -> None:
        self._scheduler.add_job(
            func=self._peak_message_loop,
            trigger="date",
            run_date=datetime.datetime.now(),
            id=f"{self._name}-{index}",
            args=[index],
        )

    def _peak_message_loop(self, index: int) -> None:
        while True:
            time.sleep(LISTENER_SEEK_INTERVAL_SECONDS)
            if self._stop_event.is_set():
                break

            message = self._queue_client.pop()
            if message is None:
                continue
            self._logger.info("Processing queue message from worker %d: %s", index, message.id)
            try:
                self._handler.handle(message)
                self._logger.info("Processed queue message from worker %d: %s", index, message.id)
            except Exception:
                self._logger.exception("Queue message processing failed: %s", message.id)

    def _create_queue_client(self, name: str) -> PollingQueueClient:
        return AzureStorageQueueClient(name, self._config)
       
