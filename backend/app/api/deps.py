"""Shared API-route helpers (Phase 4A).

Centralized translation of service-layer errors to HTTP, so route
handlers stay thin and error semantics stay consistent:

  - TaskNotFound     → 404 (generic)
  - InvalidAssignee  → sanitized 400 (no user IDs echoed)

AuthorizationDenied is NOT handled here — it maps through the
centralized FastAPI exception handler in ``app.main`` (HTTP 403,
generic body).
"""

from contextlib import contextmanager

from fastapi import HTTPException, status

from app.services.tasks import InvalidAssignee, TaskNotFound


@contextmanager
def map_service_errors():
    """Translate service-layer exceptions to their HTTP contracts."""
    try:
        yield
    except TaskNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )
    except InvalidAssignee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid assignee"
        )
