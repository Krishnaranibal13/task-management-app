"""Authentication routes: login, logout, session probe.

Approved surface only. No registration, reset, recovery, MFA, or
account-management endpoints exist.

Security invariants enforced here:
  - generic 401 for unknown email AND wrong password (equivalent
    verification work via dummy hash)
  - the raw session credential never appears in JSON (cookie only)
  - logout revokes server-side state authoritatively and is CSRF-protected
  - security events are logged WITHOUT passwords, hashes, tokens,
    cookies, or request/response bodies
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.auth import rate_limit, session_service
from app.auth.dependencies import get_current_session, get_current_user, require_csrf
from app.auth.schemas import LoginRequest, LoginResponse, LogoutResponse, MeResponse
from app.auth.security import hash_password, verify_dummy_for_unknown_email, verify_password  # noqa: F401
from app.auth.session_model import AuthSession
from app.core.config import settings
from app.db.session import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _session_cookie_kwargs() -> dict:
    """Cookie attributes per approved contract; lifetime stays synced with
    the server-side session when configuration provides one."""
    lifetime = settings.SESSION_LIFETIME_SECONDS
    kwargs = {
        "key": settings.SESSION_COOKIE_NAME,
        "httponly": True,                    # no JavaScript access
        "secure": settings.cookie_secure,    # true in production only
        "samesite": "lax",
        "path": "/",
    }
    if lifetime is not None:
        kwargs["max_age"] = lifetime
    return kwargs


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: OrmSession = Depends(get_db),
) -> LoginResponse:
    """Email + password → session cookie + CSRF token (JSON)."""
    rate_limit.check_rate_limit(request, payload.email)

    user = db.execute(
        select(User).where(User.email == payload.email.strip().lower())
    ).scalar_one_or_none()

    if user is None:
        # Equivalent Argon2id verification work; identical outward contract.
        verify_dummy_for_unknown_email(payload.password)
        rate_limit.record_failed_attempt(request, payload.email)
        # Generic reason only: no account-existence signal in logs.
        _log_auth_event("auth_failure", reason="invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(payload.password, user.password_hash):
        rate_limit.record_failed_attempt(request, payload.email)
        _log_auth_event("auth_failure", reason="invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token, csrf_token, _row = session_service.create_session(db, user.id)
    response.set_cookie(value=token, **_session_cookie_kwargs())
    _log_auth_event("auth_success")
    # NOTE: the raw session token is intentionally NOT in this JSON body.
    return LoginResponse(csrf_token=csrf_token)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    response: Response,
    db: OrmSession = Depends(get_db),
    current: AuthSession = Depends(require_csrf),
) -> LogoutResponse:
    """Revoke the server-side session authoritatively, then clear cookie."""
    session_service.revoke_session(db, current)
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    _log_auth_event("logout")
    return LogoutResponse()


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:
    """Authenticated identity probe (no sensitive values)."""
    return MeResponse(user_id=user.id, email=user.email, role=user.role.value)


def _log_auth_event(event: str, **context) -> None:
    """Structured security log WITHOUT secrets of any kind.

    Never logged: passwords, hashes, session identifiers/tokens, cookies,
    CSRF tokens/secrets, request bodies, emails.
    """
    parts = [f"event={event}"]
    parts.extend(f"{k}={v}" for k, v in sorted(context.items()))
    print("[security] " + " ".join(parts), flush=True)
