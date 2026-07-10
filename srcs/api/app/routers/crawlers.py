"""Crawler integration routes."""

from fastapi import APIRouter

from app.core.exceptions import NotImplementException

router = APIRouter(prefix="/api/crawlers", tags=["crawlers"])


@router.get("")
def list_crawlers() -> dict[str, object]:
    """Placeholder for the crawler registry endpoint."""

    raise NotImplementException("Crawler registry is not implemented yet")

