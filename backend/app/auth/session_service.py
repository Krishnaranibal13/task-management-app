"""Session and CSRF token creation/lookup/revocation.

Security properties:
  - Session credential: ``secrets.token_urlsafe(32)`` — 32 random bytes
    from a cryptographically secure generator (≈256 bits of entropy).
  - Raw credentials are NEVER persisted: only SHA-256 digests.
  - The CSRF token is a separate cryptographically generated value,
    distinct from the session credential; only its digest is stored.
  - Session creation REQUIRES a configured positive lifetime. There is
    deliberately NO fallback lifetime: an unconfigured/invalid lifetime
    is a server-side configuration error and must fail closed (no
    long-lived session is ever invented).
"""

import datetime
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.session_model import AuthSession
from app.core.config import settings


def utcnow_naive() -> datetime.datetime:
    """UTC timestamp without tzinfo (matches MySQL DATETIME storage)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def generate_session_token() -> str:
    """Opaque session credential (never stored raw server-side)."""
    return secrets.token_urlsafe(32)


def generate_csrf_token() -> str:
    """Cryptographically random CSRF token bound to a session."""
    return secrets.token_urlsafe(32)


def digest(token: str) -> str:
    """SHA-256 hex digest of a credential."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _configured_lifetime_seconds() -> int:
    """Return the configured session lifetime; fail closed if unset.

    A missing or non-positive lifetime is a deployment configuration
    error. We raise a server-side error (surfaced to clients only as a
    generic failure) rather than inventing any effective lifetime.
    """
    lifetime = settings.SESSION_LIFETIME_SECONDS
    if lifetime is None or int(lifetime) <= 0:
        raise RuntimeError(
            "Session lifetime is not configured: SESSION_LIFETIME_SECONDS "
            "must be set to a positive integer before sessions can be created."
        )
    return int(lifetime)


def create_session(db: Session, user_id: int) -> tuple[str, str, AuthSession]:
    """Create an active session for the user.

    Returns ``(session_token, csrf_token, row)``. Only digests persist;
    the caller places the session token in the cookie and returns the
    CSRF token to the client in the JSON body. Cookie Max-Age and
    ``expires_at`` derive from the SAME configured lifetime.
    """
    lifetime = _configured_lifetime_seconds()
    token = generate_session_token()
    csrf = generate_csrf_token()
    expires = utcnow_naive() + datetime.timedelta(seconds=lifetime)
    row = AuthSession(
        token_digest=digest(token),
        user_id=user_id,
        csrf_token_digest=digest(csrf),
        expires_at=expires,
    )
    db.add(row)
    db.commit()
    return token, csrf, row


def get_active_session_by_token(db: Session, token: str | None) -> AuthSession | None:
    """Return the active session for a raw credential, else None.

    None covers: missing credential, unknown session, expired session,
    revoked session — all indistinguishable to the caller by design.
    """
    if not token:
        return None
    stmt = select(AuthSession).where(
        AuthSession.token_digest == digest(token),
        AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > utcnow_naive(),
    )
    return db.execute(stmt).scalar_one_or_none()


def revoke_session(db: Session, session_row: AuthSession) -> None:
    """Server-side logout invalidation (authoritative)."""
    session_row.revoked_at = utcnow_naive()
    db.commit()


def rotate_csrf_token(db: Session, session_row: AuthSession) -> str:
    """Issue a fresh CSRF token for an EXISTING active session.

    Phase 4C bootstrap capability: after a browser/SPA refresh the
    HttpOnly session cookie survives but in-memory CSRF state is lost,
    so an authenticated client needs a new synchronizer token for its
    CURRENT session.

    Behavior:
      - generates a fresh cryptographically secure token (same
        generator as login-time issuance),
      - replaces ONLY this session's stored CSRF digest,
      - leaves session id (token digest), user identity, creation time,
        and expiration policy untouched — no lifetime extension,
      - implicitly invalidates the previously issued token for THIS
        session (the old raw value no longer matches the stored digest),
      - never persists or logs the raw token; only its digest remains,
      - does not modify any OTHER session row.
    """
    fresh = generate_csrf_token()
    session_row.csrf_token_digest = digest(fresh)
    db.commit()
    return fresh
