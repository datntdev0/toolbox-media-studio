"""In-memory cache provider tests."""

from datetime import UTC, datetime

from app.providers.cache_provider import InMemoryCacheProvider


def test_in_memory_cache_provider_keys_records_by_cache_type() -> None:
    current_time = datetime(2026, 7, 11, tzinfo=UTC)
    cache = InMemoryCacheProvider(clock=lambda: current_time)
    canonical_url = "https://www.novel543.com/0603625457/dir"

    cache.set("crawler:novel543:html", canonical_url, "<html></html>")
    cache.set("crawler:novel543:metadata", canonical_url, {"title": "Cached"})

    assert cache.get("crawler:novel543:html", canonical_url) == "<html></html>"
    assert cache.get("crawler:novel543:metadata", canonical_url) == {"title": "Cached"}
