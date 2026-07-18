from typing import Annotated

from fastapi.params import Depends

from app.core.config.app_config import AppConfig
from app.core.logging import LogManager
from app.providers.cache_provider import CacheProvider, build_cosmos_cache_provider
from app.providers.proxy_service_provider import ProxyProvider, build_proxy_provider
from app.repositories.cosmosdb.cosmos_novel_repository import build_cosmos_novel_repository
from app.repositories.cosmosdb.cosmos_user_repository import build_cosmos_user_repository
from app.repositories.novel_repository import NovelRepository
from app.repositories.user_repository import UserRepository

log_manager = LogManager() # Singleton instance of Logger
config = AppConfig() # Singleton instance of AppConfig

# Repository instances can be registered
repository_user = build_cosmos_user_repository(config)
repository_novel = build_cosmos_novel_repository(config)

# Provider instances can be registered
provider_proxy = build_proxy_provider(config)
provider_cache = build_cosmos_cache_provider(config)

# Dependency injection for FastAPI routes

LogManagerDep = Annotated[LogManager, Depends(lambda: log_manager)]

RepositoryUserDep = Annotated[UserRepository, Depends(lambda: repository_user)]
RepositoryNovelDep = Annotated[NovelRepository, Depends(lambda: repository_novel)]

ProviderCacheDep = Annotated[CacheProvider, Depends(lambda: provider_cache)]
ProviderProxyDep = Annotated[ProxyProvider, Depends(lambda: provider_proxy)]
