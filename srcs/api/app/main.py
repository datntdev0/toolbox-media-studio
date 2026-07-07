"""FastAPI application factory."""

from contextlib import asynccontextmanager

import app.core.startup_checks as startup_checks
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import auth, health


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        startup_checks.validate_external_connections(settings)
        yield

    app = FastAPI(
        title="Novel Media Studio API",
        version="0.1.0",
        summary="Domain API — authentication slice",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_allowed_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)

    return app


app = create_app()
