from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config.app_config import AppConfig
from app.core.exceptions.handler import global_exception_handlers
from app.core.injection import (
    config,
    log_manager,
    provider_cache,
    provider_proxy,
    provider_public_blob,
    queue_listener_scraping,
    queue_publisher,
    queue_subscriber_sample,
    repository_novel,
    repository_scraping,
    repository_scraping_result,
    repository_user,
)
from app.events.scraping_handler import requeue_stale_scrapings
from app.routers import auth, crawlers, health, novels, scrapings, users

app_config = AppConfig()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_manager.configure()
    logger = log_manager.getLogger()

    app.state.logger = logger  # Store the logger instance in app state
    app.state.config = config  # Store the app config instance in app state
    app.state.repository_user = repository_user  # Store the user repository instance in app state
    app.state.repository_novel = repository_novel
    app.state.repository_scraping = repository_scraping
    app.state.repository_scraping_result = repository_scraping_result
    app.state.provider_cache = provider_cache  # Backward-compatible cache provider state name
    app.state.provider_proxy = provider_proxy  # Store the proxy provider instance in app state
    app.state.provider_public_blob = provider_public_blob
    app.state.queue_subscriber_sample = queue_subscriber_sample
    app.state.queue_listener_scraping = queue_listener_scraping

    from app.core.security.authentication import seed_admin_user
    seed_admin_user(logger, app_config, repository_user)

    queue_subscriber_sample.start()
    try:
        requeue_stale_scrapings(repository_scraping, queue_publisher)
    except Exception:
        logger.exception("Stale Scrapings could not be requeued")
    queue_listener_scraping.start()

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

app = FastAPI(lifespan=lifespan)

app.add_middleware(CORSMiddleware,
    allow_origins=app_config.security.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(Exception, global_exception_handlers)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(novels.router)
app.include_router(crawlers.router)
app.include_router(scrapings.router)

app.title = app_config.appName
