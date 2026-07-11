"""Global FastAPI exception handlers."""

from __future__ import annotations

from pathlib import Path
from traceback import extract_tb

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import NotImplementException
from app.core.logging import get_logger

logger = get_logger("exception_handlers")


def register_exception_handlers(app: FastAPI) -> None:
    """Register shared exception handlers for the application."""

    app.add_exception_handler(NotImplementException, _handle_not_implement_exception)
    app.add_exception_handler(Exception, _handle_unhandled_exception)


async def _handle_not_implement_exception(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a standard 501 response for placeholder endpoints."""

    return JSONResponse(
        status_code=501,
        content=_build_error_payload(
            code=501,
            message=str(exc) or "Not implemented",
            exc=exc,
        ),
    )


async def _handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Return a standard 500 response for unexpected failures."""

    logger.exception("Unhandled exception while processing request")
    return JSONResponse(
        status_code=500,
        content=_build_error_payload(
            code=500,
            message="Internal Server Error",
            exc=exc,
        ),
    )


def _build_error_payload(code: int, message: str, exc: BaseException) -> dict[str, object]:
    """Build the shared error response body."""

    return {
        "code": code,
        "message": message,
        "traceStack": _format_traceback(exc),
    }


def _format_traceback(exc: BaseException) -> list[str]:
    """Render the current exception traceback as a list of lines."""

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
