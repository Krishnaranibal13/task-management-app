"""Health check routes."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe. Reports process liveness only — no auth required."""
    return {"status": "ok"}
