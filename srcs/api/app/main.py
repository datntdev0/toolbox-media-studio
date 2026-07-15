from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config.app_settings import AppSettings
from app.core.logger import Logger

appSettings = AppSettings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Logger().configure()
    logger = Logger().getLogger()
    logger.info("Starting application lifespan...")
    yield

app = FastAPI(lifespan=lifespan)

from app.routers import health
app.include_router(health.router)

app.title = appSettings.appName