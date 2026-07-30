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
from app.events.translation_handler import TranslationQueueListener
from app.providers.blob_storage_provider import PublicBlobProvider, build_public_blob_provider
from app.providers.cache_provider import CacheProvider, build_cosmos_cache_provider
from app.providers.proxy_service_provider import ProxyProvider, build_proxy_provider
from app.providers.translation_service_provider import (
    TranslationServiceProviderFactory,
    build_translation_service_provider_factory,
)
from app.repositories.cosmosdb.cosmos_novel_chapter_repository import (
    build_cosmos_novel_chapter_repository,
)
from app.repositories.cosmosdb.cosmos_novel_repository import build_cosmos_novel_repository
from app.repositories.cosmosdb.cosmos_scraping_repository import (
    build_cosmos_scraping_repository,
)
from app.repositories.cosmosdb.cosmos_scraping_result_repository import (
    build_cosmos_scraping_result_repository,
)
from app.repositories.cosmosdb.cosmos_translation_repository import (
    build_cosmos_translation_repository,
)
from app.repositories.cosmosdb.cosmos_translation_result_repository import (
    build_cosmos_translation_result_repository,
)
from app.repositories.cosmosdb.cosmos_user_repository import build_cosmos_user_repository
from app.repositories.novel_chapter_repository import NovelChapterRepository
from app.repositories.novel_repository import NovelRepository
from app.repositories.scraping_repository import ScrapingRepository
from app.repositories.scraping_result_repository import ScrapingResultRepository
from app.repositories.translation_repository import TranslationRepository
from app.repositories.translation_result_repository import TranslationResultRepository
from app.repositories.user_repository import UserRepository
from app.services.novel_binding_service import NovelBindingService
from app.services.translation_service import TranslationService

log_manager = LogManager() # Singleton instance of Logger
config = AppConfig() # Singleton instance of AppConfig

# Repository instances can be registered
repository_user = build_cosmos_user_repository(config)
repository_novel = build_cosmos_novel_repository(config)
repository_scraping = build_cosmos_scraping_repository(config)
repository_scraping_result = build_cosmos_scraping_result_repository(config)
repository_translation = build_cosmos_translation_repository(config)
repository_translation_result = build_cosmos_translation_result_repository(config)
# Lazily constructed so existing API/test setups that do not use novel chapters
# do not require the new Cosmos container.
repository_novel_chapter: NovelChapterRepository | None = None

# Provider instances can be registered
provider_proxy = build_proxy_provider(config)
provider_public_blob = build_public_blob_provider(config)
provider_cache = build_cosmos_cache_provider(config)
provider_translation_service_factory = build_translation_service_provider_factory(config)
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
    workers=1,
)

# Dependency injection for FastAPI routes

LogManagerDep = Annotated[LogManager, Depends(lambda: log_manager)]

RepositoryUserDep = Annotated[UserRepository, Depends(lambda: repository_user)]
RepositoryNovelDep = Annotated[NovelRepository, Depends(lambda: repository_novel)]
RepositoryTranslationDep = Annotated[
    TranslationRepository,
    Depends(lambda: repository_translation),
]
RepositoryTranslationResultDep = Annotated[
    TranslationResultRepository,
    Depends(lambda: repository_translation_result),
]
RepositoryScrapingDep = Annotated[
    ScrapingRepository,
    Depends(lambda: repository_scraping),
]
RepositoryScrapingResultDep = Annotated[
    ScrapingResultRepository,
    Depends(lambda: repository_scraping_result),
]


def _get_novel_chapter_repository() -> NovelChapterRepository:
    global repository_novel_chapter
    if repository_novel_chapter is None:
        repository_novel_chapter = build_cosmos_novel_chapter_repository(config)
    return repository_novel_chapter


def _get_novel_binding_service() -> NovelBindingService:
    return NovelBindingService(
        repository_novel,
        repository_scraping,
        repository_scraping_result,
        _get_novel_chapter_repository(),
    )


def _get_translation_service() -> TranslationService:
    return TranslationService(
        repository_translation,
        repository_novel,
        _get_novel_chapter_repository(),
        repository_translation_result,
    )


queue_listener_translation = TranslationQueueListener(
    logger=log_manager.getLogger("queue.translations"),
    translation_repository=repository_translation,
    translation_result_repository=repository_translation_result,
    novel_chapter_repository=_get_novel_chapter_repository(),
    realtime_hub=realtime_hub,
    translation_service_provider_factory=provider_translation_service_factory,
    workers=1,
)


RepositoryNovelChapterDep = Annotated[
    NovelChapterRepository,
    Depends(_get_novel_chapter_repository),
]
ServiceNovelBindingDep = Annotated[
    NovelBindingService,
    Depends(_get_novel_binding_service),
]
ServiceTranslationDep = Annotated[
    TranslationService,
    Depends(_get_translation_service),
]

ProviderCacheDep = Annotated[CacheProvider, Depends(lambda: provider_cache)]
ProviderProxyDep = Annotated[ProxyProvider, Depends(lambda: provider_proxy)]
ProviderTranslationServiceFactoryDep = Annotated[
    TranslationServiceProviderFactory,
    Depends(lambda: provider_translation_service_factory),
]
ProviderPublicBlobDep = Annotated[PublicBlobProvider, Depends(lambda: provider_public_blob)]
PollingQueuePublisherDep = Annotated[PollingQueuePublisher, Depends(lambda: queue_publisher)]
RealtimeHubDep = Annotated[RealtimeHub, Depends(lambda: realtime_hub)]
