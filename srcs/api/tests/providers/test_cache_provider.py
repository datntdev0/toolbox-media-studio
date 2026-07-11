"""Cache provider tests."""

from datetime import UTC, datetime, timedelta

from app.providers.cache_provider import RepositoryCacheProvider
from app.repositories.cache_repository import InMemoryCacheRepository


def test_cache_provider_expires_items_from_created_at_and_configured_ttl() -> None:
    current_time = datetime(2026, 7, 11, tzinfo=UTC)
    cache = RepositoryCacheProvider(
        repository=InMemoryCacheRepository(),
        ttl_seconds=60,
        clock=lambda: current_time,
    )
    cache.set("crawler:novel543:html", "https://www.novel543.com/0603625457/", "<html></html>")

    assert cache.get("crawler:novel543:html", "https://www.novel543.com/0603625457/") == (
        "<html></html>"
    )

    current_time += timedelta(seconds=61)
    assert cache.get("crawler:novel543:html", "https://www.novel543.com/0603625457/") is None
