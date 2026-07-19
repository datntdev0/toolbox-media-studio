import logging
from pathlib import Path
from typing import Any

from app.core.config.app_config import AppConfig
from shared.decorators import singleton

LOGGER_NAME = "toolbox_media_studio_api"

@singleton
class LogManager:
    
    def __init__(self):
        self.__mainLogger = logging.getLogger(LOGGER_NAME)

    def configure(self) -> None:
        settings = AppConfig()
        configure_logging(settings, self.__mainLogger)

    def getLogger(self, name: str | None = None) -> logging.Logger:
        return self.__mainLogger if name is None else self.__mainLogger.getChild(name)


    def cast_int(self, value: object) -> int:
        if isinstance(value, int):
            return value
        return logging.INFO
    

    def coerce_level(self, level: str) -> int:
        normalized = level.upper()
        return self.cast_int(getattr(logging, normalized, logging.INFO))


def configure_logging(
    settings: Any,
    logger: logging.Logger | None = None,
) -> logging.Logger:
    """Configure console and optional file logging for the API logger."""

    target_logger = logger or logging.getLogger(LOGGER_NAME)
    log_level = getattr(settings, "logLevel", getattr(settings, "log_level", "INFO"))
    target_logger.setLevel(_coerce_level(str(log_level)))

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(target_logger.level)
    console_handler.setFormatter(formatter)

    target_logger.handlers.clear()
    target_logger.addHandler(console_handler)

    log_file_path = getattr(settings, "log_file_path", None)
    if log_file_path:
        path = Path(str(log_file_path))
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setLevel(target_logger.level)
        file_handler.setFormatter(formatter)
        target_logger.addHandler(file_handler)

    return target_logger


def _coerce_level(level: str) -> int:
    normalized = level.upper()
    value = getattr(logging, normalized, logging.INFO)
    return value if isinstance(value, int) else logging.INFO
