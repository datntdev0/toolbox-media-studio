"""Application logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import Settings

LOGGER_NAME = "toolbox_media_studio_api"


def configure_logging(settings: Settings) -> logging.Logger:
    """Configure and return the shared application logger."""

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(_coerce_level(settings.log_level))
    logger.propagate = False

    if getattr(logger, "_toolbox_configured", False):
        return logger

    log_path = Path(settings.log_file_path)
    if not log_path.is_absolute():
        log_path = Path.cwd() / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logger.level)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_048_576,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logger.level)
    file_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger._toolbox_configured = True  # type: ignore[attr-defined]

    logger.info("Logging configured", extra={"log_file_path": str(log_path)})
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the shared application logger or a named child logger."""

    logger = logging.getLogger(LOGGER_NAME)
    if name is None:
        return logger
    return logger.getChild(name)


def _coerce_level(level: str) -> int:
    normalized = level.upper()
    return cast_int(getattr(logging, normalized, logging.INFO))


def cast_int(value: object) -> int:
    """Keep mypy happy when reading stdlib logging constants dynamically."""

    if isinstance(value, int):
        return value
    return logging.INFO
