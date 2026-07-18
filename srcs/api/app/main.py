from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config.app_config import AppConfig
from app.core.exceptions.handler import global_exception_handlers

from app.core.injection.service_provider import log_manager, config
from app.core.injection.service_provider import repository_user, repository_novel, repository_cache
from app.core.injection.service_provider import provider_cache

app_config = AppConfig()

@asynccontextmanager
async def lifespan(app: FastAPI):
    log_manager.configure()
    logger = log_manager.getLogger()

    app.state.logger = logger  # Store the logger instance in app state
    app.state.config = config  # Store the app config instance in app state
    app.state.repository_user = repository_user  # Store the user repository instance in app state
    app.state.repository_novel = repository_novel  # Store the novel repository instance in app state
    app.state.repository_cache = repository_cache  # Store the cache repository instance in app state
    app.state.provider_cache = provider_cache  # Store the cache provider instance in app state

    from app.core.security.authentication import seed_admin_user
    seed_admin_user(logger, app_config, repository_user)

    yield

app = FastAPI(lifespan=lifespan)

app.add_exception_handler(Exception, global_exception_handlers)

from app.routers import health, auth, users, novels
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(novels.router)

app.title = app_config.appName
