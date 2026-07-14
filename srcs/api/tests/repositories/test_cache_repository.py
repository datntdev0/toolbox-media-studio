"""Cache repository tests."""

from datetime import UTC, datetime

from app.repositories.cache_repository import CacheRecord, InMemoryCacheRepository


def test_cache_repository_keys_records_by_cache_type() -> None:
    repository = InMemoryCacheRepository()
    canonical_url = "https://www.novel543.com/0603625457/dir"
    html_record = CacheRecord(
        cache_type="crawler:novel543:html",
        cache_key=canonical_url,
        value="<html></html>",
        created_at=datetime(2026, 7, 11, tzinfo=UTC),
    )
    metadata_record = CacheRecord(
        cache_type="crawler:novel543:metadata",
        cache_key=canonical_url,
        value={"title": "Cached"},
        created_at=datetime(2026, 7, 11, tzinfo=UTC),
    )

    repository.upsert(html_record)
    repository.upsert(metadata_record)

    assert repository.get("crawler:novel543:html", canonical_url) == html_record
    assert repository.get("crawler:novel543:metadata", canonical_url) == metadata_record
