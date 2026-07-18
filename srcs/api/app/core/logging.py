import logging

from app.core.config.app_config import AppConfig
from shared.decorators import singleton

LOGGER_NAME = "toolbox_media_studio_api"

@singleton
class LogManager:
    
    def __init__(self):
        self.__mainLogger = logging.getLogger(LOGGER_NAME)

    def configure(self) -> None:
        settings = AppConfig()

        self.__mainLogger.setLevel(self.coerce_level(settings.logLevel))

        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.__mainLogger.level)
        console_handler.setFormatter(formatter)

        self.__mainLogger.handlers.clear()
        self.__mainLogger.addHandler(console_handler)


    def getLogger(self, name: str | None = None) -> logging.Logger:
        return self.__mainLogger if name is None else self.__mainLogger.getChild(name)


    def cast_int(self, value: object) -> int:
        if isinstance(value, int):
            return value
        return logging.INFO
    

    def coerce_level(self, level: str) -> int:
        normalized = level.upper()
        return self.cast_int(getattr(logging, normalized, logging.INFO))
