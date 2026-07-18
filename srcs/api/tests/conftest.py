"""Shared pytest fixtures."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest

from app.core.config.app_config import AppConfig
from app.providers.cache_provider import InMemoryCacheProvider
from app.repositories.job_repository import InMemoryJobRepository
from app.repositories.novel_repository import InMemoryNovelRepository
from app.repositories.user_repository import InMemoryUserRepository

TEST_ADMIN_EMAIL = "admin@example.com"
TEST_ADMIN_PASSWORD = "s3cret-pass"


@dataclass(slots=True)
class FakeFlareSolverrResult:
    """Minimal fake FlareSolverr result for tests."""

    html: str


@dataclass(frozen=True, slots=True)
class SentQueueMessage:
    """Minimal sent queue message for tests."""

    id: str


@dataclass(frozen=True, slots=True)
class ReceivedQueueMessage:
    """Minimal received queue message for tests."""

    id: str
    pop_receipt: str
    body: Mapping[str, Any]


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


class FakeQueueProvider:
    """In-memory queue provider for route tests."""

    def __init__(self, queue_name: str) -> None:
        self._queue_name = queue_name
        self.messages: list[Mapping[str, Any]] = []
        self.ensure_count = 0
        self.raise_on_send: Exception | None = None

    @property
    def queue_name(self) -> str:
        return self._queue_name

    def ensure_exists(self) -> None:
        self.ensure_count += 1

    def send(self, message: Mapping[str, Any]) -> SentQueueMessage:
        if self.raise_on_send is not None:
            raise self.raise_on_send
        self.messages.append(dict(message))
        return SentQueueMessage(id=str(len(self.messages)))

    def receive_one(self, visibility_timeout: int) -> ReceivedQueueMessage | None:
        del visibility_timeout
        return None

    def retry(self, message: ReceivedQueueMessage, visibility_timeout: int) -> None:
        del message, visibility_timeout

    def delete(self, message: ReceivedQueueMessage) -> None:
        del message


class FakeQueueProviderFactory:
    """Queue provider factory keyed by queue name."""

    def __init__(self) -> None:
        self.providers: dict[str, FakeQueueProvider] = {}

    def get(self, queue_name: str) -> FakeQueueProvider:
        provider = self.providers.get(queue_name)
        if provider is None:
            provider = FakeQueueProvider(queue_name)
            self.providers[queue_name] = provider
        return provider


class FakeQueuePublisher:
    """In-memory queue publisher for route tests."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, Mapping[str, Any]]] = []

    def publish(self, queue_name: str, message: Mapping[str, Any]) -> None:
        self.messages.append((queue_name, dict(message)))


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required env vars before settings are constructed.

    Environment variables take priority over any local `.env` file in pydantic-settings,
    so these values are what the app sees during tests.
    """
    monkeypatch.setenv("FAST_SECURITY_DEFAULT_ADMIN_EMAIL", TEST_ADMIN_EMAIL)
    monkeypatch.setenv("FAST_SECURITY_DEFAULT_ADMIN_PASSWORD", TEST_ADMIN_PASSWORD)
    monkeypatch.setenv("FAST_JWT_SIGNING_KEY", "test-signing-key-please-ignore")
    monkeypatch.setenv("FAST_JWT_EXPIRE_MINUTES", "120")
    monkeypatch.setenv("FAST_SECURITY_JWT_SIGNING_KEY", "test-signing-key-please-ignore")
    monkeypatch.setenv("FAST_SECURITY_JWT_EXPIRE_MINUTES", "120")
    monkeypatch.setenv("FAST_LOG_LEVEL", "INFO")
    monkeypatch.setenv("FAST_LOG_FILE_PATH", "logs/test-api.log")
    monkeypatch.setenv("FAST_ENVIRONMENT", "localhost")
    monkeypatch.setenv("FAST_FLARESOLVERR_BASE_URL", "http://localhost:8191/v1")
    monkeypatch.setenv("FAST_FLARESOLVERR_MAX_TIMEOUT_MS", "60000")
    monkeypatch.setenv("FAST_CACHE_TTL_SECONDS_CRAWLER", "2592000")
    monkeypatch.setenv(
        "FAST_AZ_CONNECTION_STRING_COSMOSDB",
        (
            "AccountEndpoint=https://localhost:8081/;"
            "AccountKey=C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
        ),
    )
    monkeypatch.setenv("FAST_AZ_COSMOSDB_DATABASE_NAME", "mediastudio")
    monkeypatch.setenv(
        "FAST_AZ_CONNECTION_STRING_STORAGE_BLOB",
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey="
        "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/"
        "KBHBeksoGMGw==;BlobEndpoint=http://localhost:10000/devstoreaccount1;",
    )
    monkeypatch.setenv(
        "FAST_AZ_CONNECTION_STRING_STORAGE_QUEUE",
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey="
        "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/"
        "KBHBeksoGMGw==;QueueEndpoint=http://localhost:10001/devstoreaccount1;",
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
def job_repository() -> InMemoryJobRepository:
    """Shared in-memory job repository for a test app instance."""

    return InMemoryJobRepository()


@pytest.fixture
def queue_provider_factory() -> FakeQueueProviderFactory:
    """Shared fake queue provider factory for a test app instance."""

    return FakeQueueProviderFactory()


@pytest.fixture
def queue_publisher() -> FakeQueuePublisher:
    """Shared fake queue publisher for a test app instance."""

    return FakeQueuePublisher()


@pytest.fixture
def cache_provider() -> InMemoryCacheProvider:
    """Shared in-memory cache provider for a test app instance."""

    return InMemoryCacheProvider(ttl_seconds=AppConfig().cache.ttl_default)


@pytest.fixture
def flaresolverr_client() -> FakeFlareSolverrClient:
    """Shared fake FlareSolverr client for a test app instance."""

    return FakeFlareSolverrClient()


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    _env: None,
    user_repository: InMemoryUserRepository,
    novel_repository: InMemoryNovelRepository,
    job_repository: InMemoryJobRepository,
    queue_provider_factory: FakeQueueProviderFactory,
    queue_publisher: FakeQueuePublisher,
    cache_provider: InMemoryCacheProvider,
    flaresolverr_client: FakeFlareSolverrClient,
):
    """A TestClient with a fresh app and cleared settings cache."""
    from fastapi.testclient import TestClient

    monkeypatch.setattr(
        "app.repositories.cosmosdb.cosmos_user_repository.build_cosmos_user_repository",
        lambda config: user_repository,
    )
    monkeypatch.setattr(
        "app.repositories.cosmosdb.cosmos_novel_repository.build_cosmos_novel_repository",
        lambda config: novel_repository,
    )
    monkeypatch.setattr(
        "app.providers.cache_provider.build_cosmos_cache_provider",
        lambda config: cache_provider,
    )

    import app.core.injection as service_provider
    import app.main as main_module
    import app.routers.health as health_router

    service_provider.repository_user = user_repository
    service_provider.repository_novel = novel_repository
    service_provider.provider_cache = cache_provider
    service_provider.provider_proxy = flaresolverr_client
    service_provider.queue_publisher = queue_publisher

    main_module.repository_user = user_repository
    main_module.repository_novel = novel_repository
    main_module.provider_cache = cache_provider
    main_module.provider_proxy = flaresolverr_client

    monkeypatch.setattr(health_router, "_check_cosmos", lambda logger, settings: True)
    monkeypatch.setattr(health_router, "_check_blob_storage", lambda logger, settings: True)
    monkeypatch.setattr(health_router, "_check_queue_storage", lambda logger, settings: True)

    with TestClient(main_module.app) as test_client:
        yield test_client
