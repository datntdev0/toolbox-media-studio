from typing import Annotated

from fastapi.params import Depends

from app.core.logging import LogManager
from app.providers.cache_provider import RepositoryCacheProvider
from app.repositories.cache_repository import CacheRepository
from app.repositories.novel_repository import NovelRepository
from app.repositories.user_repository import UserRepository
from app.repositories.cosmosdb.cosmos_cache_repository import build_cosmos_cache_repository
from app.repositories.cosmosdb.cosmos_novel_repository import build_cosmos_novel_repository
from app.repositories.cosmosdb.cosmos_user_repository import build_cosmos_user_repository
from app.core.config.app_config import AppConfig

log_manager = LogManager() # Singleton instance of Logger
config = AppConfig() # Singleton instance of AppConfig

# Repository instances can be registered
repository_user = build_cosmos_user_repository(config)
repository_novel = build_cosmos_novel_repository(config)
repository_cache = build_cosmos_cache_repository(config)

# Provider instances can be registered
provider_cache = RepositoryCacheProvider(config, repository_cache)

# Dependency injection for FastAPI routes

LogManagerDep = Annotated[LogManager, Depends(lambda: log_manager)]

RepositoryUserDep = Annotated[UserRepository, Depends(lambda: repository_user)]
RepositoryNovelDep = Annotated[NovelRepository, Depends(lambda: repository_novel)]
RepositoryCacheDep = Annotated[CacheRepository, Depends(lambda: repository_cache)]

ProviderCacheDep = Annotated[RepositoryCacheProvider, Depends(lambda: provider_cache)]
