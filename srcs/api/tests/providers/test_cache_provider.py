"""Cache provider tests."""

from datetime import UTC, datetime, timedelta

from app.providers.cache_provider import InMemoryCacheProvider


def test_cache_provider_expires_items_from_created_at_and_configured_ttl() -> None:
    current_time = datetime(2026, 7, 11, tzinfo=UTC)
    cache = InMemoryCacheProvider(
        ttl_seconds=60,
        clock=lambda: current_time,
    )
    cache_key = "https://www.novel543.com/0603625457/dir"
    cache.set("crawler:novel543:html", cache_key, "<html></html>")

    assert cache.get("crawler:novel543:html", cache_key) == "<html></html>"

    current_time += timedelta(seconds=61)
    assert cache.get("crawler:novel543:html", cache_key) is None
