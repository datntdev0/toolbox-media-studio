"""Cache provider tests."""

from datetime import UTC, datetime, timedelta

from app.core.config.app_config import CACHE_TTL_CRAWLER, CACHE_TTL_DEFAULT
from app.providers.cache_provider import InMemoryCacheProvider


def test_cache_provider_expires_items_from_created_at_and_default_ttl() -> None:
    current_time = datetime(2026, 7, 11, tzinfo=UTC)
    cache = InMemoryCacheProvider(
        clock=lambda: current_time,
    )
    cache_key = "https://www.novel543.com/0603625457/dir"
    cache.set("ui:dashboard", cache_key, {"status": "fresh"})

    assert cache.get("ui:dashboard", cache_key) == {"status": "fresh"}

    current_time += timedelta(seconds=CACHE_TTL_DEFAULT + 1)
    assert cache.get("ui:dashboard", cache_key) is None


def test_cache_provider_uses_crawler_ttl_for_crawler_cache_types() -> None:
    current_time = datetime(2026, 7, 11, tzinfo=UTC)
    cache = InMemoryCacheProvider(
        clock=lambda: current_time,
    )
    cache_key = "https://www.novel543.com/0603625457/dir"

    cache.set("crawler:novel543:html", cache_key, "<html></html>")
    cache.set("ui:dashboard", "latest", {"status": "fresh"})

    current_time += timedelta(seconds=CACHE_TTL_DEFAULT + 1)

    assert cache.get("crawler:novel543:html", cache_key) == "<html></html>"
    assert cache.get("ui:dashboard", "latest") is None

    current_time = datetime(2026, 7, 11, tzinfo=UTC) + timedelta(
        seconds=CACHE_TTL_CRAWLER + 1
    )

    assert cache.get("crawler:novel543:html", cache_key) is None
