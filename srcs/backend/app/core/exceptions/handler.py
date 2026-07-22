"""Global FastAPI exception handlers."""

from __future__ import annotations

from pathlib import Path
from traceback import extract_tb
from typing import cast

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core import logging
from app.core.config.app_config import AppConfig
from app.core.exceptions import NotImplementException

settings = AppConfig()  # Singleton instance of AppSettings

async def global_exception_handlers(request: Request, exc: Exception) -> JSONResponse:
    status_code = {
        NotImplementException: 501,
    }.get(type(exc), 500)

    logger = cast(logging.Logger, request.state.logger)
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


def _format_traceback(exc: BaseException) -> list[str]:
    """Render the current exception traceback as a list of lines."""
    if settings.environment == "production": return []
    if exc.__traceback__ is None: return []

    lines: list[str] = ["Traceback (most recent call last):"]
    for frame in extract_tb(exc.__traceback__):
        filename = Path(frame.filename).name
        lines.append(f'  File "{filename}", line {frame.lineno}, in {frame.name}')
        if frame.line:
            lines.append(f"    {frame.line.strip()}")
    lines.append(f"{type(exc).__name__}: {exc}")
    return lines
