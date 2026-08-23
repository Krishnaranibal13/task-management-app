"""Login rate limiting (Phase 3A).

Contract:
  - Threshold and window are configuration; when unconfigured, limiting
    is DISABLED (no invented production values). Tests inject explicit
    test-only values via ``configure_for_tests``.
  - When the configured threshold within the window is exceeded for a
    given source (IP) AND target account key, login returns HTTP 429.

Storage: an in-process fixed-window counter keyed by (ip, email).
This is a LOCAL/TEST PROTOTYPE mechanism and is NOT production-ready:
a multi-worker production deployment requires shared rate-limit
infrastructure (e.g. Redis), which is deliberately NOT introduced in
Phase 3A. Production shared storage remains an explicit
pre-production architecture/configuration decision and this limiter
must not be represented as sufficient for production.
"""

import datetime
import threading

from fastapi import HTTPException, Request, status

from app.core.config import settings

_lock = threading.Lock()
_attempts: dict[tuple[str, str], list[datetime.datetime]] = {}


def _client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def configure_for_tests(max_attempts: int | None, window_seconds: int | None) -> None:
    """Inject TEST-ONLY thresholds; also used to reset state between tests."""
    settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS = max_attempts
    settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS = window_seconds
    with _lock:
        _attempts.clear()


def _enabled() -> bool:
    return (
        settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS is not None
        and settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS is not None
        and settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS > 0
        and settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS > 0
    )


def check_rate_limit(request: Request, email_key: str) -> None:
    """Raise HTTP 429 when the configured threshold is already reached.

    Check-only: this does NOT record an attempt. Failed logins are
    recorded exactly once via ``record_failed_attempt`` so successful
    logins never consume throttle quota.
    """
    if not _enabled():
        return
    key = (_client_ip(request), email_key.strip().lower())
    now = datetime.datetime.now(datetime.timezone.utc)
    window = datetime.timedelta(seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
    with _lock:
        bucket = [t for t in _attempts.get(key, []) if now - t < window]
        _attempts[key] = bucket
        if len(bucket) >= int(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS):  # type: ignore[arg-type]
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts",
            )


def record_failed_attempt(request: Request, email_key: str) -> None:
    """Record a failed attempt against the throttle bucket."""
    if not _enabled():
        return
    key = (_client_ip(request), email_key.strip().lower())
    now = datetime.datetime.now(datetime.timezone.utc)
    with _lock:
        _attempts.setdefault(key, []).append(now)
