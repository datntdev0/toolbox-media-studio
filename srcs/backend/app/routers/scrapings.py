"""Scraping routes with direct HTTP orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Path, Query, Response, status

from app.core.injection import (
    PollingQueuePublisherDep,
    ProviderCacheDep,
    ProviderProxyDep,
    RepositoryScrapingDep,
    RepositoryScrapingResultDep,
)
from app.core.security.authorization import SessionUser
from app.domain.scraping_results import ScrapingResultResponse, to_scraping_result_response
from app.domain.scrapings import (
    Scraping,
    ScrapingCreateRequest,
    ScrapingCreateResponse,
    ScrapingDetailResponse,
    ScrapingListResponse,
    ScrapingMetadata,
    ScrapingProgress,
    ScrapingStatus,
    ScrapingTask,
    ScrapingTaskStatus,
    to_scraping_detail,
    to_scraping_summary,
)
from app.events.scraping_handler import (
    SCRAPING_QUEUE_NAME,
    build_scraping_event,
)
from app.providers.crawler_provider import (
    CrawlerFetchError,
    CrawlerFetchTimeoutError,
    InvalidCrawlerUrlError,
    UnknownCrawlerError,
    fetch_metadata,
)
from app.repositories.scraping_repository import (
    ScrapingContinuationTokenError,
    ScrapingNotFoundError,
    ScrapingTooLargeError,
)

router = APIRouter(prefix="/api/scrapings", tags=["scrapings"])


@router.post(
    "",
    response_model=ScrapingCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="create_scraping",
)
def create_scraping_route(
    session_user: SessionUser,
    repository_scraping: RepositoryScrapingDep,
    provider_cache: ProviderCacheDep,
    provider_proxy: ProviderProxyDep,
    queue_publisher: PollingQueuePublisherDep,
    response: Response,
    body: ScrapingCreateRequest,
) -> ScrapingCreateResponse:
    """Create or reuse a Scraping and publish newly created work."""

    try:
        crawler_metadata = fetch_metadata(
            crawler_id=body.crawler_id,
            source_url=body.source_url,
            cache_provider=provider_cache,
            proxy_provider=provider_proxy,
        )
    except UnknownCrawlerError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crawler not found",
        ) from exc
    except InvalidCrawlerUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except CrawlerFetchTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Crawler source timed out",
        ) from exc
    except CrawlerFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Crawler source could not be fetched",
        ) from exc

    now = datetime.now(UTC)
    idempotency_key = _idempotency_key(
        session_user.id,
        crawler_metadata.crawler_id,
        crawler_metadata.source_url,
    )
    tasks = [
        ScrapingTask(
            id=_task_id(chapter.url),
            source_url=chapter.url,
            title=chapter.title,
            chapter_number=chapter.chapter_number,
            manifest_index=index,
        )
        for index, chapter in enumerate(crawler_metadata.chapters)
    ]
    candidate = Scraping(
        id=str(uuid4()),
        crawler_id=crawler_metadata.crawler_id,
        source_url=crawler_metadata.source_url,
        metadata=ScrapingMetadata(
            source_novel_id=crawler_metadata.source_novel_id,
            title=crawler_metadata.title,
            author=crawler_metadata.author,
            category=crawler_metadata.category,
            updated_date=crawler_metadata.updated_date,
            protagonists=list(crawler_metadata.protagonists),
            description=crawler_metadata.description,
            cover_image_url=crawler_metadata.cover_image_url,
            fetched_at=crawler_metadata.fetched_at,
        ),
        status=ScrapingStatus.QUEUED,
        tasks=tasks,
        progress=ScrapingProgress.from_tasks(tasks),
        attempts=0,
        last_error=None,
        idempotency_key=idempotency_key,
        active_key=idempotency_key,
        created_by=session_user.id,
        created_at=now,
        updated_at=now,
    )

    try:
        create_result = repository_scraping.create_or_get_active(candidate)
    except ScrapingTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    scraping = create_result.scraping
    if create_result.created:
        try:
            queue_publisher.publish(
                SCRAPING_QUEUE_NAME,
                build_scraping_event(scraping),
            )
        except Exception as exc:
            repository_scraping.set_status(
                scraping.id,
                scraping.created_by,
                ScrapingStatus.FAILED,
                error="Event publication failed",
                etag=scraping.etag,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Scraping could not be queued",
            ) from exc

    response.headers["Location"] = f"/api/scrapings/{scraping.id}"
    summary = to_scraping_summary(scraping)
    return ScrapingCreateResponse(
        **summary.model_dump(),
        reused=not create_result.created,
    )


@router.get(
    "",
    response_model=ScrapingListResponse,
    operation_id="list_scrapings",
)
def list_scrapings_route(
    session_user: SessionUser,
    repository_scraping: RepositoryScrapingDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    continuation_token: Annotated[str | None, Query(alias="continuationToken")] = None,
    scraping_status: Annotated[ScrapingStatus | None, Query(alias="status")] = None,
) -> ScrapingListResponse:
    """List Scrapings."""

    del session_user
    try:
        page = repository_scraping.list(
            created_by=None,
            limit=limit,
            continuation_token=continuation_token,
            status=scraping_status,
        )
    except ScrapingContinuationTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return ScrapingListResponse(
        items=[to_scraping_summary(scraping) for scraping in page.items],
        continuation_token=page.continuation_token,
    )


@router.get(
    "/{id}",
    response_model=ScrapingDetailResponse,
    operation_id="get_scraping",
)
def get_scraping_route(
    session_user: SessionUser,
    repository_scraping: RepositoryScrapingDep,
    id: str,
) -> ScrapingDetailResponse:
    """Return one Scraping with embedded tasks."""

    del session_user
    scraping = repository_scraping.get(id)
    if scraping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraping not found",
        )
    return to_scraping_detail(scraping)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_scraping",
)
def delete_scraping_route(
    session_user: SessionUser,
    repository_scraping: RepositoryScrapingDep,
    repository_scraping_result: RepositoryScrapingResultDep,
    id: str,
) -> Response:
    """Delete one Scraping and its results."""

    del session_user
    scraping = repository_scraping.get(id)
    if scraping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraping not found",
        )
    try:
        repository_scraping_result.delete_by_scraping(scraping.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scraping results could not be deleted",
        ) from exc
    try:
        repository_scraping.delete(scraping.id, scraping.created_by)
    except ScrapingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraping not found",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{id}/results/{taskId}",
    response_model=ScrapingResultResponse,
    operation_id="get_scraping_result",
)
def get_scraping_result_route(
    session_user: SessionUser,
    repository_scraping: RepositoryScrapingDep,
    repository_scraping_result: RepositoryScrapingResultDep,
    id: str,
    task_id: Annotated[str, Path(alias="taskId")],
) -> ScrapingResultResponse:
    """Return the isolated result for one completed embedded task."""

    del session_user
    scraping = repository_scraping.get(id)
    if scraping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraping not found",
        )
    task = next((item for item in scraping.tasks if item.id == task_id), None)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraping task not found",
        )
    if task.status != ScrapingTaskStatus.COMPLETED or not task.result_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scraping result is not available",
        )
    try:
        result = repository_scraping_result.get(scraping.id, task.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scraping result is unavailable",
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scraping result is unavailable",
        )
    return to_scraping_result_response(result)


def _idempotency_key(created_by: str, crawler_id: str, source_url: str) -> str:
    digest = sha256(f"{created_by}\n{crawler_id}\n{source_url}\nall".encode()).hexdigest()
    return f"sha256:{digest}"


def _task_id(source_url: str) -> str:
    return f"sha256:{sha256(source_url.encode('utf-8')).hexdigest()}"
