from typing import Annotated

from fastapi.params import Depends

from app.core.logging import LogManager
from app.repositories.cosmosdb.cosmos_user_repository import build_cosmos_user_repository
from app.core.config.app_config import AppConfig
from app.repositories.user_repository import UserRepository

log_manager = LogManager() # Singleton instance of Logger
config = AppConfig() # Singleton instance of AppConfig

# Repository instances can be registered
repository_user = build_cosmos_user_repository(config)

# Dependency injection for FastAPI routes

LogManagerDep = Annotated[LogManager, Depends(lambda: log_manager)]

RepositoryUserDep = Annotated[UserRepository, Depends(lambda: repository_user)]

