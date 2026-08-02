from __future__ import annotations

import logging
from pathlib import Path
from traceback import extract_tb
from typing import cast

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config.app_config import AppConfig
from app.core.exceptions import (
    AlreadyExistsException,
    BadGatewayException,
    ConflictException,
    GatewayTimeoutException,
    NotFoundException,
    NotImplementException,
    ServiceUnavailableException,
    StateConflictException,
    UnauthorizedException,
    ValidationException,
)

settings = AppConfig()  # Singleton instance of AppSettings

async def global_exception_handlers(request: Request, exc: Exception) -> JSONResponse:
    status_code = _resolve_status_code(exc)

    logger = cast(logging.Logger, request.app.state.logger)
    logger.exception("Unhandled exception: %s", exc)

    return JSONResponse(
        status_code=status_code,
        content=_build_error_payload(
            message=exc.args[0] if exc.args else str(exc),
            exc=exc,
        ),
    )

def _build_error_payload(message: str, exc: BaseException) -> dict[str, object]:
    """Build the shared error response body."""

    return {
        "message": message,
        "traceStack": _format_traceback(exc),
    }


def _resolve_status_code(exc: Exception) -> int:
    if isinstance(exc, NotImplementException):
        return 501
    if isinstance(exc, UnauthorizedException):
        return 401
    if isinstance(exc, NotFoundException):
        return 404
    if isinstance(exc, AlreadyExistsException):
        return 409
    if isinstance(exc, StateConflictException):
        return 409
    if isinstance(exc, ConflictException):
        return 412
    if isinstance(exc, ValidationException):
        return 422
    if isinstance(exc, BadGatewayException):
        return 502
    if isinstance(exc, ServiceUnavailableException):
        return 503
    if isinstance(exc, GatewayTimeoutException):
        return 504
    return 500


def _format_traceback(exc: BaseException) -> list[str]:
    """Render the current exception traceback as a list of lines."""
    if settings.environment == "production":
        return []
    if exc.__traceback__ is None:
        return []

    lines: list[str] = ["Traceback (most recent call last):"]
    for frame in extract_tb(exc.__traceback__):
        filename = Path(frame.filename).name
        lines.append(f'  File "{filename}", line {frame.lineno}, in {frame.name}')
        if frame.line:
            lines.append(f"    {frame.line.strip()}")
    lines.append(f"{type(exc).__name__}: {exc}")
    return lines
