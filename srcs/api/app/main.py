from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config.app_config import AppConfig
from app.core.exceptions.handler import global_exception_handlers

from app.core.injection.service_provider import log_manager, config
from app.core.injection.service_provider import repository_user

appSettings = AppConfig()

@asynccontextmanager
async def lifespan(app: FastAPI):
    log_manager.configure()
    logger = log_manager.getLogger()

    app.state.logger = logger  # Store the logger instance in app state
    app.state.config = config  # Store the app config instance in app state
    app.state.repository_user = repository_user  # Store the user repository instance in app state

    from app.core.security.authentication import seed_admin_user
    seed_admin_user(logger, appSettings, repository_user)

    yield

app = FastAPI(lifespan=lifespan)

app.add_exception_handler(Exception, global_exception_handlers)

from app.routers import health, auth, users
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)

app.title = appSettings.appName