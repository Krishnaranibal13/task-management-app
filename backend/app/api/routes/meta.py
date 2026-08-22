"""Public metadata endpoint."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["meta"])


@router.get("/api/meta")
def meta() -> dict[str, str]:
    """Non-sensitive build metadata."""
    return {
        "service": settings.PROJECT_NAME,
        "version": "0.1.0",
        "phase": "foundation",
        "environment": settings.ENVIRONMENT,
    }
