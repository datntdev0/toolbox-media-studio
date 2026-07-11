"""Shared pytest fixtures."""

from dataclasses import dataclass

import pytest

from app.providers.cache_provider import RepositoryCacheProvider
from app.repositories.cache_repository import InMemoryCacheRepository
from app.repositories.novel_repository import InMemoryNovelRepository
from app.repositories.user_repository import InMemoryUserRepository

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "s3cret-pass"


@dataclass(slots=True)
class FakeFlareSolverrResult:
    """Minimal fake FlareSolverr result for tests."""

    html: str


class FakeFlareSolverrClient:
    """Controllable fake FlareSolverr client for tests."""

    def __init__(self) -> None:
        self.html = "<html><body><h1>Test Novel</h1></body></html>"
        self.calls: list[tuple[str, int | None]] = []
        self.exception: Exception | None = None

    def get(self, url: str, max_timeout_ms: int | None = None) -> FakeFlareSolverrResult:
        self.calls.append((url, max_timeout_ms))
        if self.exception is not None:
            raise self.exception
        return FakeFlareSolverrResult(html=self.html)


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required env vars before settings are constructed.

    Environment variables take priority over any local `.env` file in pydantic-settings,
    so these values are what the app sees during tests.
    """
    monkeypatch.setenv("ADMIN_EMAIL", ADMIN_EMAIL)
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN_PASSWORD)
    monkeypatch.setenv("JWT_SIGNING_KEY", "test-signing-key-please-ignore")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "60")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("LOG_FILE_PATH", "logs/test-api.log")
    monkeypatch.setenv("ENVIRONMENT", "localhost")
    monkeypatch.setenv("FLARESOLVERR_BASE_URL", "http://localhost:8191/v1")
    monkeypatch.setenv("FLARESOLVERR_MAX_TIMEOUT_MS", "60000")
    monkeypatch.setenv("CRAWLER_CACHE_TTL_SECONDS", "2592000")
    monkeypatch.setenv(
        "AZ_COSMOSDB_CONNECTION_STRING",
        (
            "AccountEndpoint=https://localhost:8081/;"
            "AccountKey=C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
        ),
    )
    monkeypatch.setenv("AZ_COSMOSDB_DATABASE_NAME", "mediastudio")
    monkeypatch.setenv(
        "AZ_STORAGE_BLOB_CONNECTION_STRING",
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey="
        "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/"
        "KBHBeksoGMGw==;BlobEndpoint=http://localhost:10000/devstoreaccount1;",
    )
    monkeypatch.setenv(
        "AZ_STORAGE_QUEUE_CONNECTION_STRING",
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey="
        "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/"
        "KBHBeksoGMGw==;QueueEndpoint=http://localhost:10001/devstoreaccount1;",
    )
    monkeypatch.setattr(
        "app.core.startup.validate_external_connections",
        lambda settings: None,
    )


@pytest.fixture
def user_repository() -> InMemoryUserRepository:
    """Shared in-memory repository for a test app instance."""

    return InMemoryUserRepository()


@pytest.fixture
def novel_repository() -> InMemoryNovelRepository:
    """Shared in-memory novel repository for a test app instance."""

    return InMemoryNovelRepository()


@pytest.fixture
def cache_provider() -> RepositoryCacheProvider:
    """Shared in-memory cache provider for a test app instance."""

    return RepositoryCacheProvider(
        repository=InMemoryCacheRepository(),
        ttl_seconds=2_592_000,
    )


@pytest.fixture
def flaresolverr_client() -> FakeFlareSolverrClient:
    """Shared fake FlareSolverr client for a test app instance."""

    return FakeFlareSolverrClient()


@pytest.fixture
def client(
    _env: None,
    user_repository: InMemoryUserRepository,
    novel_repository: InMemoryNovelRepository,
    cache_provider: RepositoryCacheProvider,
    flaresolverr_client: FakeFlareSolverrClient,
):
    """A TestClient with a fresh app and cleared settings cache."""
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    with TestClient(
        create_app(
            user_repository=user_repository,
            novel_repository=novel_repository,
            cache_provider=cache_provider,
            flaresolverr_client=flaresolverr_client,
        )
    ) as test_client:
        yield test_client
    get_settings.cache_clear()
