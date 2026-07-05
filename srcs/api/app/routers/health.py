"""Health / readiness routes."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness/readiness probe for deployment verification."""
    return {"status": "ok"}
