"""HTTP authorization contract tests (Phase 3B final correction).

Proves the CENTRALIZED ``AuthorizationDenied`` → HTTP 403 mapping using
TEST-ONLY probe routes mounted on an isolated app instance. No
production Task/Comment routes exist; these probes are defined here so
the contract is executable without inventing product features.

Contract verified:
  - authenticated denial            → 403 (generic sanitized body)
  - missing/invalid session         → 401 (Phase 3A behavior preserved;
                                      the 403 handler must NOT intercept)
  - expired/revoked sessions       → still 401 on real Phase 3A endpoints
  - AuthorizationDenied             → never leaks as HTTP 500
  - internal reasons/ids/roles      → never in any response body
"""

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.auth.authorization import (
    AuthorizationDenied,
    can_add_comment,
    can_create_task,
    can_update_task_status,
    require_authenticated_user,
)
from app.core.config import settings


class _TaskStub:
    """Minimal server-loaded assignment stand-in."""

    def __init__(self, assignee_id):
        self.assignee_id = assignee_id


@pytest.fixture()
def authz_env(db_engine):
    """App instance with TEST-ONLY probe routes, bound to taskdb_test."""
    from app.auth.dependencies import get_current_user
    from app.auth.security import hash_password  # noqa: F401 (used by tests)
    from app.db.session import get_db
    from app.main import create_app

    app = create_app()

    @app.get("/test-authz/pm-only")
    async def pm_only_route(user=Depends(get_current_user)):  # pragma: no cover
        can_create_task(user)  # PM-only policy
        return {"ok": True}

    @app.get("/test-authz/dev-status")
    async def dev_status_route(
        assignee_id: int = None, user=Depends(get_current_user)
    ):
        can_update_task_status(user, _TaskStub(assignee_id))
        return {"ok": True}

    @app.get("/test-authz/defensive")
    async def defensive_route():
        # Direct invocation of the defensive guard (no HTTP auth layer):
        # must surface as 403 through the central handler, NEVER as 500.
        require_authenticated_user(None)
        return {"ok": True}

    saved_lifetime = settings.SESSION_LIFETIME_SECONDS
    settings.SESSION_LIFETIME_SECONDS = 3600  # test-only value

    SM = sessionmaker(bind=db_engine, expire_on_commit=False)

    def _override_get_db():
        s = SM()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield app, TestClient(app)
    finally:
        app.dependency_overrides.clear()
        settings.SESSION_LIFETIME_SECONDS = saved_lifetime


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["csrf_token"]


# --- A/B/E: authenticated denial → sanitized 403, never 500 ---------------


def test_developer_denied_on_pm_only_route_403_sanitized(
    authz_env, make_user
) -> None:
    from app.auth.security import hash_password

    _, client = authz_env
    marker_pw = "pw123456"
    make_user(
        "dev403@example.com", "developer", password_hash=hash_password(marker_pw)
    )
    _login(client, "dev403@example.com", marker_pw)

    resp = client.get("/test-authz/pm-only")
    # A + E: denied (not 200), correctly mapped (not 500).
    assert resp.status_code == 403
    # B: EXACTLY the generic body — no reason strings, roles, ids, emails.
    assert resp.json() == {"detail": "Forbidden"}
    body = resp.text.lower()
    for forbidden in (
        "pm_required",
        "role_not_permitted",
        "developer_not_assigned",
        "authenticated_user_required",
        "dev403@example.com",
        "password",
        marker_pw,
    ):
        assert forbidden not in body


def test_developer_denied_on_unassigned_status_probe_403(
    authz_env, make_user
) -> None:
    from app.auth.security import hash_password

    _, client = authz_env
    make_user(
        "devst@example.com", "developer", password_hash=hash_password("pw123456")
    )
    _login(client, "devst@example.com", "pw123456")

    resp = client.get("/test-authz/dev-status")  # assignee_id=None default
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Forbidden"}


def test_defensive_guard_path_never_becomes_500(authz_env) -> None:
    _, client = authz_env
    resp = client.get("/test-authz/defensive")
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Forbidden"}


# --- allow-path sanity through HTTP ----------------------------------------


def test_developer_allowed_on_own_assigned_status_probe(
    authz_env, make_user, db_session
) -> None:
    from app.auth.security import hash_password

    _, client = authz_env
    make_user(
        "devown@example.com", "developer", password_hash=hash_password("pw123456")
    )
    _login(client, "devown@example.com", "pw123456")
    uid = db_session.execute(
        text("SELECT id FROM users WHERE email = 'devown@example.com'")
    ).scalar_one()

    resp = client.get(f"/test-authz/dev-status?assignee_id={uid}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# --- C: Phase 3A 401 behavior fully preserved -------------------------------


def test_missing_session_on_real_endpoint_remains_401(authz_env) -> None:
    _, client = authz_env
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/logout").status_code == 401


def test_missing_session_on_protected_probe_is_401_not_403(authz_env) -> None:
    """The 403 handler must not swallow authentication failures."""
    _, client = authz_env
    resp = client.get("/test-authz/pm-only")  # no cookie at all
    assert resp.status_code == 401


def test_unknown_session_token_remains_401(authz_env) -> None:
    _, client = authz_env
    client.cookies.set(settings.SESSION_COOKIE_NAME, "totally-unknown-token-value")
    assert client.get("/api/auth/me").status_code == 401


# --- D: expired/revoked sessions remain 401 --------------------------------


def test_revoked_session_still_401_after_authorization_layer(
    authz_env, make_user, db_session
) -> None:
    from app.auth.security import hash_password

    _, client = authz_env
    email = "revoke403@example.com"
    make_user(email, "pm", password_hash=hash_password("pw123456"))
    _login(client, email, "pw123456")

    sid = db_session.execute(
        text(
            "SELECT s.id FROM auth_sessions s JOIN users u ON u.id = s.user_id "
            "WHERE u.email = :e"
        ),
        {"e": email},
    ).scalar_one()
    db_session.execute(
        text("UPDATE auth_sessions SET revoked_at = NOW() WHERE id = :i"),
        {"i": sid},
    )
    db_session.commit()

    assert client.get("/api/auth/me").status_code == 401


def test_expired_session_still_401_after_authorization_layer(
    authz_env, make_user, db_session
) -> None:
    from datetime import datetime, timedelta

    from app.auth.security import hash_password

    _, client = authz_env
    email = "expire403@example.com"
    make_user(email, "pm", password_hash=hash_password("pw123456"))
    _login(client, email, "pw123456")

    sid = db_session.execute(
        text(
            "SELECT s.id FROM auth_sessions s JOIN users u ON u.id = s.user_id "
            "WHERE u.email = :e"
        ),
        {"e": email},
    ).scalar_one()
    db_session.execute(
        text(
            "UPDATE auth_sessions SET expires_at = :past WHERE id = :i"
        ),
        {"past": datetime.utcnow() - timedelta(minutes=1), "i": sid},
    )
    db_session.commit()

    assert client.get("/api/auth/me").status_code == 401


# --- F: policy matrix unchanged (compact smoke; full matrix in
# tests/test_authorization.py) ------------------------------------------------


def test_policy_matrix_smoke_unchanged() -> None:
    class _U:
        def __init__(self, uid, role):
            self.id = uid
            self.role = role

    pm, dev = _U(1, "pm"), _U(2, "developer")
    can_add_comment(pm)
    can_add_comment(dev)
    can_create_task(pm)
    with pytest.raises(AuthorizationDenied):
        can_create_task(dev)
    with pytest.raises(AuthorizationDenied):
        can_update_task_status(dev, _TaskStub(None))
    can_update_task_status(dev, _TaskStub(2))
