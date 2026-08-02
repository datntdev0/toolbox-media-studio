from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config.app_config import AppConfig
from app.core.exceptions import (
    AlreadyExistsException,
    BadGatewayException,
    ConflictException,
    GatewayTimeoutException,
    NotFoundException,
    NotImplementException,
    ServiceUnavailableException,
    StateConflictException,
    UnauthorizedException,
    ValidationException,
)
from app.core.exceptions.handler import global_exception_handlers
from app.core.injection import (
    config,
    log_manager,
    provider_cache,
    provider_proxy,
    provider_public_blob,
    queue_listener_scraping,
    queue_listener_translation,
    queue_listener_workspace,
    queue_subscriber_sample,
    realtime_hub,
    repository_novel,
    repository_scraping,
    repository_scraping_result,
    repository_translation,
    repository_translation_result,
    repository_user,
    repository_workspace,
    repository_workspace_result,
)
from app.routers import auth, health, novels, realtime, scrapings, translations, users, workspaces

app_config = AppConfig()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_manager.configure()
    logger = log_manager.getLogger()

    app.state.logger = logger  # Store the logger instance in app state
    app.state.config = config  # Store the app config instance in app state
    app.state.repository_user = repository_user  # Store the user repository instance in app state
    app.state.repository_novel = repository_novel
    app.state.repository_translation = repository_translation
    app.state.repository_translation_result = repository_translation_result
    app.state.repository_workspace = repository_workspace
    app.state.repository_workspace_result = repository_workspace_result
    app.state.repository_scraping = repository_scraping
    app.state.repository_scraping_result = repository_scraping_result
    app.state.provider_cache = provider_cache  # Backward-compatible cache provider state name
    app.state.provider_proxy = provider_proxy  # Store the proxy provider instance in app state
    app.state.provider_public_blob = provider_public_blob
    app.state.queue_subscriber_sample = queue_subscriber_sample
    app.state.queue_listener_scraping = queue_listener_scraping
    app.state.queue_listener_translation = queue_listener_translation
    app.state.queue_listener_workspace = queue_listener_workspace
    app.state.realtime_hub = realtime_hub

    from app.core.security.authentication import seed_admin_user
    seed_admin_user(logger, app_config, repository_user)

    # queue_subscriber_sample.start()
    # queue_listener_scraping.start()
    # queue_listener_translation.start()
    # queue_listener_workspace.start()

    try:
        yield
    finally:
        try:
            queue_subscriber_sample.stop()
        except Exception:
            logger.exception("Sample queue subscriber failed to stop")
        try:
            queue_listener_scraping.stop()
        except Exception:
            logger.exception("Scraping queue listener failed to stop")
        try:
            queue_listener_translation.stop()
        except Exception:
            logger.exception("Translation queue listener failed to stop")
        try:
            queue_listener_workspace.stop()
        except Exception:
            logger.exception("Workspace task queue listener failed to stop")
        await realtime_hub.close_all()

app = FastAPI(lifespan=lifespan)

app.add_middleware(CORSMiddleware,
    allow_origins=app_config.security.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(NotImplementException, global_exception_handlers)
app.add_exception_handler(UnauthorizedException, global_exception_handlers)
app.add_exception_handler(NotFoundException, global_exception_handlers)
app.add_exception_handler(AlreadyExistsException, global_exception_handlers)
app.add_exception_handler(ConflictException, global_exception_handlers)
app.add_exception_handler(StateConflictException, global_exception_handlers)
app.add_exception_handler(ValidationException, global_exception_handlers)
app.add_exception_handler(BadGatewayException, global_exception_handlers)
app.add_exception_handler(ServiceUnavailableException, global_exception_handlers)
app.add_exception_handler(GatewayTimeoutException, global_exception_handlers)
app.add_exception_handler(Exception, global_exception_handlers)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(novels.router)
app.include_router(translations.router)
app.include_router(workspaces.router)
app.include_router(scrapings.router)
app.include_router(realtime.router)

app.title = app_config.appName
