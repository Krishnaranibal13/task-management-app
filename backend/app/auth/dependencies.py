"""FastAPI dependencies for session authentication and CSRF validation.

Missing / unknown / expired / revoked sessions all reduce to the same
outcome: HTTP 401 with a generic body.
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as OrmSession

from app.auth.origin_validation import validate_request_origin
from app.auth.session_model import AuthSession
from app.auth import session_service
from app.core.config import settings
from app.db.session import get_db


def _session_cookie_name() -> str:
    return settings.SESSION_COOKIE_NAME


def get_session_token(request: Request) -> str | None:
    """Extract the opaque credential from cookies only."""
    return request.cookies.get(_session_cookie_name())


def get_current_session(
    request: Request,
    token: str | None = Depends(get_session_token),
    db: OrmSession = Depends(get_db),
) -> AuthSession:
    """Resolve an ACTIVE server-side session or raise generic 401."""
    row = session_service.get_active_session_by_token(db, token)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return row


def get_current_user(db: OrmSession = Depends(get_db), current: AuthSession = Depends(get_current_session)):
    """The authenticated user for the active session."""
    from app.models import User

    user = db.get(User, current.user_id)
    if user is None:  # defensive: dangling infrastructure row
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_csrf(
    request: Request,
    db: OrmSession = Depends(get_db),
    current: AuthSession = Depends(get_current_session),
) -> AuthSession:
    """Validate Origin/Referer defense-in-depth, then the synchronizer token.

    SEC-MED-01: centralized Origin/Referer validation for state-changing
    requests (POST/PUT/PATCH/DELETE) runs FIRST and is ADDITIONAL — it
    never replaces the session-bound synchronizer-token check below.
    Token arrives in the ``X-CSRF-Token`` header and must match the
    digest bound to THIS session. Missing/invalid/foreign-session tokens
    all yield 403. Tokens are never logged.

    Every approved mutating endpoint (logout, task create/update/status/
    delete, comment create, developer /status) depends on this single
    dependency, so the defense applies uniformly with no per-route logic.
    """
    validate_request_origin(request)

    presented = request.headers.get("X-CSRF-Token", "")
    if not presented or not secrets_compare_digest(
        session_service.digest(presented), current.csrf_token_digest
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )
    return current


def secrets_compare_digest(a: str, b: str) -> bool:
    """Constant-time string comparison wrapper."""
    import hmac

    return hmac.compare_digest(a, b)
