"""Authenticated, bidirectional WebSocket endpoint."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.core.config.app_config import AppConfig
from app.core.injection import RepositoryUserDep, realtime_hub
from app.core.realtime import RealtimeConnection
from app.core.security.jwt_helper import decode_access_token
from app.domain.users import UserStatus

router = APIRouter(tags=["realtime"])
app_config = AppConfig()


@router.websocket("/api/ws")
async def realtime_socket(
    websocket: WebSocket,
    repository_user: RepositoryUserDep,
    access_token: Annotated[str | None, Query(alias="accessToken")] = None,
) -> None:
    """Keep one authenticated, typed-message socket open for the web application."""

    if not _origin_allowed(websocket) or not access_token:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    try:
        claims = decode_access_token(access_token)
    except JWTError:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    subject = claims.get("sub")
    user = repository_user.get_by_id(str(subject)) if subject else None
    if user is None or user.status != UserStatus.ACTIVE:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    await websocket.accept()
    connection = realtime_hub.connect(
        websocket,
        user_id=user.id,
        loop=asyncio.get_running_loop(),
    )
    realtime_hub.send(
        connection,
        "connection.ready",
        {"userId": user.id, "connectedAt": _now()},
    )

    sender = asyncio.create_task(_send_messages(connection))
    receiver = asyncio.create_task(_receive_messages(connection))
    try:
        done, pending = await asyncio.wait(
            {sender, receiver},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done | pending:
            with suppress(asyncio.CancelledError, RuntimeError, WebSocketDisconnect):
                await task
    finally:
        sender.cancel()
        receiver.cancel()
        await asyncio.gather(sender, receiver, return_exceptions=True)
        realtime_hub.disconnect(connection.id)


async def _send_messages(connection: RealtimeConnection) -> None:
    while True:
        await connection.websocket.send_json(await connection.messages.get())


async def _receive_messages(connection: RealtimeConnection) -> None:
    while True:
        message = await connection.websocket.receive_json()
        if not isinstance(message, dict):
            realtime_hub.send(connection, "connection.error", {"message": "Invalid message"})
            continue

        message_type = message.get("type")
        payload = message.get("payload", {})
        if not isinstance(message_type, str) or not message_type:
            realtime_hub.send(
                connection,
                "connection.error",
                {"message": "A message type is required"},
            )
        elif message_type == "connection.ping":
            realtime_hub.send(
                connection,
                "connection.pong",
                {"serverTime": _now(), "clientTime": _payload_value(payload, "clientTime")},
            )
        elif message_type == "connection.echo":
            realtime_hub.send(
                connection,
                "connection.echo",
                payload if isinstance(payload, dict) else {"value": payload},
            )
        else:
            realtime_hub.send(
                connection,
                "connection.error",
                {"message": f"Unsupported message type: {message_type}"},
            )


def _origin_allowed(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    allowed = app_config.security.cors_allowed_origins
    return not origin or not allowed or "*" in allowed or origin in allowed


def _payload_value(payload: Any, key: str) -> Any:
    return payload.get(key) if isinstance(payload, dict) else None


def _now() -> str:
    return datetime.now(UTC).isoformat()
