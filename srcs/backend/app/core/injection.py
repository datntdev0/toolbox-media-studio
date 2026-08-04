"""
This module provides dependency injection for FastAPI routes, allowing for the registration of repositories, providers, services, and queue listeners.

Conventions:
- All import statements should be grouped by type (repositories, providers, services, queue listeners) and sorted alphabetically within each group.
- All import statements must be written in single lines, with no line breaks or multi-line imports.
- All depend annotations should be defined at the bottom of the file, after all other code, and should be sorted alphabetically by name.
- All depend annotations should be written in single lines, with no line breaks or multi-line annotations.
"""
from typing import Annotated

from fastapi.params import Depends

from app.core.config.app_config import AppConfig
from app.core.events.polling_queue_publisher import AzureStorageQueuePublisher, PollingQueuePublisher
from app.core.logging import LogManager
from app.core.realtime import RealtimeHub
from app.events.sample_handler import SampleQueueListener
from app.events.scraping_handler import ScrapingQueueListener
from app.events.translation_handler import TranslationQueueListener
from app.events.workspace_handler import WorkspaceTaskQueueListener
from app.providers.blob_storage_provider import PublicBlobProvider, build_public_blob_provider
from app.providers.cache_provider import CacheProvider, build_cosmos_cache_provider
from app.providers.proxy_service_provider import ProxyProvider, build_proxy_provider
from app.providers.speech_service_provider import build_speech_service_provider
from app.providers.translation_service_provider import TranslationServiceProviderFactory, build_translation_service_provider_factory
from app.repositories.cosmosdb.cosmos_novel_chapter_repository import build_cosmos_novel_chapter_repository
from app.repositories.cosmosdb.cosmos_novel_repository import build_cosmos_novel_repository
from app.repositories.cosmosdb.cosmos_scraping_repository import build_cosmos_scraping_repository
from app.repositories.cosmosdb.cosmos_scraping_result_repository import build_cosmos_scraping_result_repository
from app.repositories.cosmosdb.cosmos_translation_repository import build_cosmos_translation_repository
from app.repositories.cosmosdb.cosmos_translation_result_repository import build_cosmos_translation_result_repository
from app.repositories.cosmosdb.cosmos_user_repository import build_cosmos_user_repository
from app.repositories.cosmosdb.cosmos_workspace_repository import build_cosmos_workspace_repository
from app.repositories.cosmosdb.cosmos_workspace_result_repository import build_cosmos_workspace_result_repository
from app.repositories.novel_chapter_repository import NovelChapterRepository
from app.repositories.novel_repository import NovelRepository
from app.repositories.scraping_repository import ScrapingRepository
from app.repositories.scraping_result_repository import ScrapingResultRepository
from app.repositories.translation_repository import TranslationRepository
from app.repositories.translation_result_repository import TranslationResultRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.repositories.workspace_result_repository import WorkspaceResultRepository
from app.services.novel_binding_service import NovelBindingService
from app.services.novel_language_service import NovelLanguageService
from app.services.workspace_service import WorkspaceService

# ============================================================================
# CONFIGURATION AND SINGLETONS
# ============================================================================

log_manager = LogManager()
config = AppConfig()

# Constants
QUEUE_WORKERS = 1

# ============================================================================
# REPOSITORY INSTANCES
# ============================================================================

repository_user = build_cosmos_user_repository(config)
repository_novel = build_cosmos_novel_repository(config)
repository_novel_chapter = build_cosmos_novel_chapter_repository(config)
repository_scraping = build_cosmos_scraping_repository(config)
repository_scraping_result = build_cosmos_scraping_result_repository(config)
repository_translation = build_cosmos_translation_repository(config)
repository_translation_result = build_cosmos_translation_result_repository(config)
repository_workspace = build_cosmos_workspace_repository(config)
repository_workspace_result = build_cosmos_workspace_result_repository(config)

# ============================================================================
# PROVIDER INSTANCES
# ============================================================================

provider_cache = build_cosmos_cache_provider(config)
provider_proxy = build_proxy_provider(config)
provider_public_blob = build_public_blob_provider(config)
provider_speech_service = build_speech_service_provider(config)
provider_translation_service_factory = build_translation_service_provider_factory(config)

# ============================================================================
# SERVICE FACTORY FUNCTIONS
# ============================================================================

def _get_novel_binding_service() -> NovelBindingService:
    """Factory function for NovelBindingService dependency injection."""
    return NovelBindingService(
        repository_novel,
        repository_scraping,
        repository_scraping_result,
        repository_novel_chapter,
    )


def _get_novel_language_service() -> NovelLanguageService:
    """Factory function for NovelLanguageService dependency injection."""
    return NovelLanguageService(
        repository_novel,
        repository_novel_chapter,
        repository_translation,
        repository_translation_result,
    )


def _get_workspace_service() -> WorkspaceService:
    """Factory function for WorkspaceService dependency injection."""
    return WorkspaceService(
        repository_workspace,
        _get_novel_language_service(),
        repository_workspace_result,
    )


# ============================================================================
# REALTIME HUB AND QUEUE SERVICES
# ============================================================================

realtime_hub = RealtimeHub()
queue_publisher = AzureStorageQueuePublisher(config)

queue_subscriber_sample = SampleQueueListener(
    logger=log_manager.getLogger("queue.sample"),
    workers=QUEUE_WORKERS,
)

queue_listener_scraping = ScrapingQueueListener(
    logger=log_manager.getLogger("queue.scrapings"),
    scraping_repository=repository_scraping,
    scraping_result_repository=repository_scraping_result,
    cache_provider=provider_cache,
    proxy_provider=provider_proxy,
    realtime_hub=realtime_hub,
    workers=QUEUE_WORKERS,
)

queue_listener_translation = TranslationQueueListener(
    logger=log_manager.getLogger("queue.translations"),
    translation_repository=repository_translation,
    translation_result_repository=repository_translation_result,
    novel_chapter_repository=repository_novel_chapter,
    realtime_hub=realtime_hub,
    translation_service_provider_factory=provider_translation_service_factory,
    workers=QUEUE_WORKERS,
)

queue_listener_workspace = WorkspaceTaskQueueListener(
    logger=log_manager.getLogger("queue.workspaces-tasks"),
    workspace_repository=repository_workspace,
    workspace_result_repository=repository_workspace_result,
    novel_language_service=_get_novel_language_service(),
    speech_provider=provider_speech_service,
    blob_provider=provider_public_blob,
    realtime_hub=realtime_hub,
    workers=QUEUE_WORKERS,
)

# ============================================================================
# DEPENDENCY INJECTION ANNOTATIONS
# ============================================================================

# Core dependencies
LogManagerDep = Annotated[LogManager, Depends(lambda: log_manager)]

# Repository dependencies - alphabetically ordered
RepositoryNovelChapterDep = Annotated[NovelChapterRepository, Depends(lambda: repository_novel_chapter)]
RepositoryNovelDep = Annotated[NovelRepository, Depends(lambda: repository_novel)]
RepositoryScrapingDep = Annotated[ScrapingRepository, Depends(lambda: repository_scraping)]
RepositoryScrapingResultDep = Annotated[ScrapingResultRepository, Depends(lambda: repository_scraping_result)]
RepositoryTranslationDep = Annotated[TranslationRepository, Depends(lambda: repository_translation)]
RepositoryTranslationResultDep = Annotated[TranslationResultRepository, Depends(lambda: repository_translation_result)]
RepositoryUserDep = Annotated[UserRepository, Depends(lambda: repository_user)]
RepositoryWorkspaceDep = Annotated[WorkspaceRepository, Depends(lambda: repository_workspace)]
RepositoryWorkspaceResultDep = Annotated[WorkspaceResultRepository, Depends(lambda: repository_workspace_result)]

# Service dependencies
ServiceNovelBindingDep = Annotated[NovelBindingService, Depends(_get_novel_binding_service)]
ServiceNovelLanguageDep = Annotated[NovelLanguageService, Depends(_get_novel_language_service)]
ServiceWorkspaceDep = Annotated[WorkspaceService, Depends(_get_workspace_service)]

# Provider dependencies - alphabetically ordered
ProviderCacheDep = Annotated[CacheProvider, Depends(lambda: provider_cache)]
ProviderProxyDep = Annotated[ProxyProvider, Depends(lambda: provider_proxy)]
ProviderPublicBlobDep = Annotated[PublicBlobProvider, Depends(lambda: provider_public_blob)]
ProviderTranslationServiceFactoryDep = Annotated[TranslationServiceProviderFactory, Depends(lambda: provider_translation_service_factory)]

# Queue and realtime dependencies
PollingQueuePublisherDep = Annotated[PollingQueuePublisher, Depends(lambda: queue_publisher)]
RealtimeHubDep = Annotated[RealtimeHub, Depends(lambda: realtime_hub)]
