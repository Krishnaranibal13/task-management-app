"""Health check route.

The approved MVP exposes a single public liveness endpoint.
A public metadata endpoint was reviewed and removed (not required by
the approved architecture).
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe. Reports process liveness only — no auth required."""
    return {"status": "ok"}
