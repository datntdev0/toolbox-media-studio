"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.startup import build_lifespan
from app.repositories.novel_repository import NovelRepository
from app.repositories.user_repository import UserRepository
from app.routers import auth, health, novels, users


def create_app(
    user_repository: UserRepository | None = None,
    novel_repository: NovelRepository | None = None,
) -> FastAPI:
    """Build and configure the FastAPI application."""

    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Novel Media Studio API",
        version="0.1.0",
        summary="Domain API — authentication, user-management, and novel-management slices",
        lifespan=build_lifespan(settings, user_repository, novel_repository),
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
    app.include_router(users.router)
    app.include_router(novels.router)

    return app
app = create_app()
