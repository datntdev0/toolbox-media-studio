"""Crawler job use-cases."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from app.core.events.polling_queue_publisher import PollingQueuePublisher
from app.domain.jobs import Job, JobKind, JobStatus
from app.domain.requests import CrawlerJobCreateRequest
from app.domain.responses import CrawlerJobResponse
from app.providers.crawler_provider import validate_source
from app.repositories.job_repository import JobRepository

CRAWLER_QUEUE_NAME = "crawler-jobs"


class CrawlerJobPublishError(Exception):
    """Raised when a newly persisted crawler job cannot be enqueued."""


def create_crawler_job(
    *,
    crawler_id: str,
    request: CrawlerJobCreateRequest,
    created_by: str,
    repository: JobRepository,
    queue_publisher: PollingQueuePublisher,
) -> CrawlerJobResponse:
    """Create or reuse an active crawler job and enqueue new work."""

    source = validate_source(crawler_id, request.url)
    now = datetime.now(UTC)
    idempotency_key = build_idempotency_key(
        relative_path=f"/api/crawlers/{source.crawler_id}/jobs",
        payload={"url": source.canonical_url},
    )
    candidate = Job(
        id=str(uuid4()),
        kind=JobKind.CRAWL,
        crawler_id=source.crawler_id,
        source_url=source.canonical_url,
        idempotency_key=idempotency_key,
        active_key=idempotency_key,
        status=JobStatus.QUEUED,
        attempts=0,
        last_error=None,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )

    result = repository.create_or_get_active(candidate)
    if result.created:
        try:
            queue_publisher.publish(CRAWLER_QUEUE_NAME, _to_queue_message(result.job))
        except Exception as exc:
            repository.mark_failed(result.job.id, result.job.created_by, 0, "Queue publish failed")
            raise CrawlerJobPublishError("Queue publish failed") from exc

    return _to_response(result.job, reused=not result.created)


def build_idempotency_key(*, relative_path: str, payload: dict[str, object]) -> str:
    """Build the crawler job idempotency key."""

    canonical_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{relative_path}\n{canonical_json}".encode()).hexdigest()
    return f"sha256:{digest}"


def _to_queue_message(job: Job) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": job.kind.value,
        "jobId": job.id,
        "crawlerId": job.crawler_id,
        "url": job.source_url,
        "createdBy": job.created_by,
        "idempotencyKey": job.idempotency_key,
        "enqueuedAt": datetime.now(UTC).isoformat(),
    }


def _to_response(job: Job, reused: bool) -> CrawlerJobResponse:
    return CrawlerJobResponse(
        id=job.id,
        kind=job.kind,
        crawler_id=job.crawler_id,
        url=job.source_url,
        status=job.status,
        attempts=job.attempts,
        reused=reused,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
