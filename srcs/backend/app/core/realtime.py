"""Application-wide WebSocket connection management."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import WebSocket

RealtimeMessage = dict[str, Any]


@dataclass(frozen=True, slots=True)
class RealtimeConnection:
    """One authenticated browser WebSocket and its event-loop-owned send queue."""

    id: str
    user_id: str
    websocket: WebSocket
    loop: asyncio.AbstractEventLoop
    messages: asyncio.Queue[RealtimeMessage]


class RealtimeHub:
    """Fan out typed messages to authenticated WebSocket connections.

    Queue consumers run in worker threads, so ``publish`` schedules queue writes
    on each connection's owning asyncio loop.
    """

    def __init__(self, queue_size: int = 100) -> None:
        self._queue_size = queue_size
        self._connections: dict[str, RealtimeConnection] = {}
        self._lock = Lock()

    def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        loop: asyncio.AbstractEventLoop,
    ) -> RealtimeConnection:
        connection = RealtimeConnection(
            id=str(uuid4()),
            user_id=user_id,
            websocket=websocket,
            loop=loop,
            messages=asyncio.Queue(maxsize=self._queue_size),
        )
        with self._lock:
            self._connections[connection.id] = connection
        return connection

    def disconnect(self, connection_id: str) -> None:
        with self._lock:
            self._connections.pop(connection_id, None)

    def publish(
        self,
        message_type: str,
        payload: dict[str, Any] | None = None,
        *,
        user_id: str | None = None,
    ) -> None:
        """Publish from either an async request or a background worker thread."""

        message: RealtimeMessage = {
            "type": message_type,
            "payload": payload or {},
        }
        with self._lock:
            connections = [
                connection
                for connection in self._connections.values()
                if user_id is None or connection.user_id == user_id
            ]

        for connection in connections:
            try:
                connection.loop.call_soon_threadsafe(
                    self._enqueue_latest,
                    connection.messages,
                    message,
                )
            except RuntimeError:
                self.disconnect(connection.id)

    def send(
        self,
        connection: RealtimeConnection,
        message_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        message: RealtimeMessage = {
            "type": message_type,
            "payload": payload or {},
        }
        try:
            connection.loop.call_soon_threadsafe(
                self._enqueue_latest,
                connection.messages,
                message,
            )
        except RuntimeError:
            self.disconnect(connection.id)

    async def close_all(self) -> None:
        with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()
        if connections:
            await asyncio.gather(
                *(
                    connection.websocket.close(code=1001, reason="Server shutting down")
                    for connection in connections
                ),
                return_exceptions=True,
            )

    @staticmethod
    def _enqueue_latest(
        queue: asyncio.Queue[RealtimeMessage],
        message: RealtimeMessage,
    ) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        queue.put_nowait(message)
