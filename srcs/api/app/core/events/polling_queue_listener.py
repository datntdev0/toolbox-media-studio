import time
import datetime

from threading import Event

from app.core.logging import get_logger

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.events.message_handler import MessageHandler
from app.core.events.polling_queue_client import AzureStorageQueueClient

LISTENER_SEEK_INTERVAL_SECONDS = 5

class PollingQueueListener:
    def __init__(self, name: str, handler: MessageHandler, workers: int = 1) -> None:
        self._name = name
        self._workers = workers
        self._handler = handler
        self._stop_event = Event()
        self._logger = get_logger(f"queue_listener.{name}")
        self._queue_client = AzureStorageQueueClient(name)
        self._scheduler = BackgroundScheduler(
            executors={"default": ThreadPoolExecutor(max_workers=workers)},
            job_defaults={"coalesce": True, "max_instances": workers},)

    def start(self) -> None:
        self._queue_client.ensure_exists()
        for i in range(self._workers): self._add_worker(i)
        self._logger.info("Starting queue listener for '%s' with %d workers", self._name, self._workers)
        self._scheduler.start()
    
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
            if message is None: continue
            self._logger.info("Processing queue message from worker %d: %s", index, message.id)
            self._handler.handle(message)
            self._logger.info("Processed queue message from worker %d: %s", index, message.id)
       