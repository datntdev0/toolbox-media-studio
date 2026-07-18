from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config.app_config import AppConfig
from app.core.exceptions.handler import global_exception_handlers
from app.core.injection import (
    config,
    log_manager,
    provider_cache,
    provider_proxy,
    repository_novel,
    repository_user,
    queue_subscriber_sample,
)
from app.routers import auth, crawlers, health, novels, users

app_config = AppConfig()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_manager.configure()
    logger = log_manager.getLogger()

    app.state.logger = logger  # Store the logger instance in app state
    app.state.config = config  # Store the app config instance in app state
    app.state.repository_user = repository_user  # Store the user repository instance in app state
    app.state.repository_novel = repository_novel
    app.state.provider_cache = provider_cache  # Backward-compatible cache provider state name
    app.state.provider_proxy = provider_proxy  # Store the proxy provider instance in app state
    app.state.queue_subscriber_sample = queue_subscriber_sample

    from app.core.security.authentication import seed_admin_user
    seed_admin_user(logger, app_config, repository_user)

    queue_subscriber_sample.start()

    try:
        yield
    finally:
        try:
            queue_subscriber_sample.stop()
        except Exception:
            logger.exception("Sample queue subscriber failed to stop")

app = FastAPI(lifespan=lifespan)

app.add_exception_handler(Exception, global_exception_handlers)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(novels.router)
app.include_router(crawlers.router)

app.title = app_config.appName
