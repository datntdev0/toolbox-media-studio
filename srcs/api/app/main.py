"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.core.startup_checks as startup_checks
from app.core.config import Settings, get_settings
from app.repositories.user_repository import UserRepository
from app.routers import auth, health, users
from app.services.user_service import seed_admin_user


def create_app(user_repository: UserRepository | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""

    settings = get_settings()

    app = FastAPI(
        title="Novel Media Studio API",
        version="0.1.0",
        summary="Domain API — authentication and user-management slices",
        lifespan=_build_lifespan(settings, user_repository),
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

    return app


def _build_lifespan(
    settings: Settings,
    provided_repository: UserRepository | None,
) -> Callable[[FastAPI], Any]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        startup_checks.validate_external_connections(settings)
        repository = provided_repository or _build_default_user_repository(settings)
        app.state.user_repository = repository
        seed_admin_user(settings, repository)
        yield

    return lifespan


def _build_default_user_repository(settings: Settings) -> UserRepository:
    from app.repositories.cosmosdb.cosmos_user_repository import build_cosmos_user_repository

    return build_cosmos_user_repository(settings)


app = create_app()
