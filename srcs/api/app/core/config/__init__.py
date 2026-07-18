"""Configuration exports."""

from app.core.config.app_config import AppConfig

Settings = AppConfig


def get_settings() -> AppConfig:
    return AppConfig()


__all__ = ["AppConfig", "Settings", "get_settings"]
