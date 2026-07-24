from typing import Annotated

from fastapi.params import Depends

from app.core.config.app_config import AppConfig
from app.core.events.polling_queue_publisher import (
    AzureStorageQueuePublisher,
    PollingQueuePublisher,
)
from app.core.logging import LogManager
from app.core.realtime import RealtimeHub
from app.events.sample_handler import SampleQueueListener
from app.events.scraping_handler import ScrapingQueueListener
from app.providers.blob_storage_provider import PublicBlobProvider, build_public_blob_provider
from app.providers.cache_provider import CacheProvider, build_cosmos_cache_provider
from app.providers.proxy_service_provider import ProxyProvider, build_proxy_provider
from app.repositories.cosmosdb.cosmos_novel_repository import build_cosmos_novel_repository
from app.repositories.cosmosdb.cosmos_scraping_repository import (
    build_cosmos_scraping_repository,
)
from app.repositories.cosmosdb.cosmos_scraping_result_repository import (
    build_cosmos_scraping_result_repository,
)
from app.repositories.cosmosdb.cosmos_user_repository import build_cosmos_user_repository
from app.repositories.novel_repository import NovelRepository
from app.repositories.scraping_repository import ScrapingRepository
from app.repositories.scraping_result_repository import ScrapingResultRepository
from app.repositories.user_repository import UserRepository

log_manager = LogManager() # Singleton instance of Logger
config = AppConfig() # Singleton instance of AppConfig

# Repository instances can be registered
repository_user = build_cosmos_user_repository(config)
repository_novel = build_cosmos_novel_repository(config)
repository_scraping = build_cosmos_scraping_repository(config)
repository_scraping_result = build_cosmos_scraping_result_repository(config)

# Provider instances can be registered
provider_proxy = build_proxy_provider(config)
provider_public_blob = build_public_blob_provider(config)
provider_cache = build_cosmos_cache_provider(config)
realtime_hub = RealtimeHub()

# Queue publishers and subscribers can be registered
queue_publisher = AzureStorageQueuePublisher(config)
queue_subscriber_sample = SampleQueueListener(log_manager.getLogger("queue.sample"), 1)
queue_listener_scraping = ScrapingQueueListener(
    logger=log_manager.getLogger("queue.scrapings"),
    scraping_repository=repository_scraping,
    scraping_result_repository=repository_scraping_result,
    cache_provider=provider_cache,
    proxy_provider=provider_proxy,
    realtime_hub=realtime_hub,
    workers=3,
)

# Dependency injection for FastAPI routes

LogManagerDep = Annotated[LogManager, Depends(lambda: log_manager)]

RepositoryUserDep = Annotated[UserRepository, Depends(lambda: repository_user)]
RepositoryNovelDep = Annotated[NovelRepository, Depends(lambda: repository_novel)]
RepositoryScrapingDep = Annotated[
    ScrapingRepository,
    Depends(lambda: repository_scraping),
]
RepositoryScrapingResultDep = Annotated[
    ScrapingResultRepository,
    Depends(lambda: repository_scraping_result),
]

ProviderCacheDep = Annotated[CacheProvider, Depends(lambda: provider_cache)]
ProviderProxyDep = Annotated[ProxyProvider, Depends(lambda: provider_proxy)]
ProviderPublicBlobDep = Annotated[PublicBlobProvider, Depends(lambda: provider_public_blob)]
PollingQueuePublisherDep = Annotated[PollingQueuePublisher, Depends(lambda: queue_publisher)]
RealtimeHubDep = Annotated[RealtimeHub, Depends(lambda: realtime_hub)]
