"""Login/logout/session/CSRF integration tests — REAL Docker MySQL.

Covers the approved Phase 3A contract:
  - generic 401 for unknown email and wrong password
  - session cookie flags (HttpOnly, SameSite=Lax, Path=/, Secure in prod)
  - raw session credential never in JSON nor persisted in MySQL
  - missing/unknown/expired/revoked sessions → 401
  - server-side logout invalidation (authoritative)
  - CSRF synchronizer token bound to the session
  - strict input: unknown fields → HTTP 400
"""

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import rate_limit
from app.auth.security import hash_password
from app.core.config import settings
from app.main import create_app


# --- login contract ------------------------------------------------------


def test_unknown_email_and_wrong_password_same_contract(api_client, make_user):
    from app.auth.security import hash_password

    make_user("known@example.com", "pm", password_hash=hash_password("right-password"))

    r1 = api_client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "whatever"},
    )
    r2 = api_client.post(
        "/api/auth/login",
        json={"email": "known@example.com", "password": "wrong"},
    )
    # Identical outward contract: same status, same generic body.
    assert r1.status_code == 401 and r2.status_code == 401
    assert r1.json() == r2.json() == {"detail": "Invalid email or password"}


def test_login_success_sets_cookie_flags(api_client, make_user):
    from app.auth.security import hash_password

    make_user("flags@example.com", "developer", password_hash=hash_password("pw"))
    resp = api_client.post(
        "/api/auth/login", json={"email": "flags@example.com", "password": "pw"}
    )
    assert resp.status_code == 200
    set_cookie = resp.headers["set-cookie"]
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()
    assert "path=/" in set_cookie.lower()
    # Raw token must NOT appear in the JSON body.
    assert "session_token" not in resp.json()


def test_login_rejects_unknown_fields_with_400(api_client):
    resp = api_client.post(
        "/api/auth/login",
        json={"email": "a@b.co", "password": "x", "role": "admin"},
    )
    assert resp.status_code == 400


def test_secure_flag_in_production_config(api_client, make_user, inject_session_settings):
    from app.auth.security import hash_password

    restore = inject_session_settings(ENVIRONMENT="production")
    try:
        make_user("prod@example.com", "pm", password_hash=hash_password("pw"))
        resp = api_client.post(
            "/api/auth/login", json={"email": "prod@example.com", "password": "pw"}
        )
        assert resp.status_code == 200
        assert "secure" in resp.headers["set-cookie"].lower()
    finally:
        restore()


def test_session_lifetime_synced_via_max_age(api_client, make_user, inject_session_settings):
    from app.auth.security import hash_password

    restore = inject_session_settings(SESSION_LIFETIME_SECONDS=3600)
    try:
        make_user("ttl@example.com", "pm", password_hash=hash_password("pw"))
        resp = api_client.post(
            "/api/auth/login", json={"email": "ttl@example.com", "password": "pw"}
        )
        assert "max-age=3600" in resp.headers["set-cookie"].lower()
    finally:
        restore()


# --- session lifecycle ---------------------------------------------------


def _login(api_client, email: str, password: str):
    return api_client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )


@pytest.fixture()
def logged_in(api_client, make_user):
    from app.auth.security import hash_password

    def _make(email="sess@example.com", password="pw123456"):
        make_user(email, "pm", password_hash=hash_password(password))
        resp = _login(api_client, email, password)
        assert resp.status_code == 200
        return resp.json()["csrf_token"]

    return _make


def test_valid_session_authenticates(api_client, logged_in):
    csrf = logged_in()
    me = api_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "pm"
    assert csrf  # token available for state-changing calls


def test_missing_session_rejected_401(api_client):
    assert api_client.get("/api/auth/me").status_code == 401


def test_unknown_session_rejected_401(api_client):
    api_client.cookies.set(settings.SESSION_COOKIE_NAME, "totally-unknown-token")
    assert api_client.get("/api/auth/me").status_code == 401


def _purge_auth_sessions(db_session) -> None:
    """Remove stale session rows so row-targeted updates hit only ours."""
    db_session.execute(text("DELETE FROM auth_sessions"))
    db_session.commit()


def test_expired_session_rejected_401(db_session, api_client, logged_in):
    csrf = logged_in(email="expired@example.com")
    # Target THIS test's session row deterministically (no LIMIT-1
    # guessing; immune to stale rows from other tests).
    row = db_session.execute(
        text(
            "SELECT s.id FROM auth_sessions s JOIN users u ON u.id = s.user_id "
            "WHERE u.email = 'expired@example.com'"
        )
    ).scalar_one()
    db_session.execute(
        text("UPDATE auth_sessions SET expires_at = :t WHERE id = :i"),
        {"t": datetime.datetime(2000, 1, 1), "i": row},
    )
    db_session.commit()
    assert api_client.get("/api/auth/me").status_code == 401


def test_raw_token_not_stored_in_mysql(db_session, api_client, logged_in):
    logged_in(email="digest@example.com")
    digests = [
        r[0] for r in db_session.execute(text("SELECT token_digest FROM auth_sessions")).all()
    ]
    cookies = api_client.cookies.get(settings.SESSION_COOKIE_NAME)
    assert cookies and all(cookies != d for d in digests)
    assert all(len(d) == 64 for d in digests)  # sha256 hex


def test_logout_revokes_server_side(api_client, logged_in):
    csrf = logged_in(email="logout@example.com")
    out = api_client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert out.status_code == 200
    # Old credential must no longer authenticate even if replayed.
    old_cookie = api_client.cookies.get(settings.SESSION_COOKIE_NAME)
    api_client.cookies.clear()
    api_client.cookies.set(settings.SESSION_COOKIE_NAME, old_cookie)
    assert api_client.get("/api/auth/me").status_code == 401


def test_revoked_session_rejected_401(db_session, api_client, logged_in):
    csrf = logged_in(email="revoke@example.com")
    row = db_session.execute(
        text(
            "SELECT s.id FROM auth_sessions s JOIN users u ON u.id = s.user_id "
            "WHERE u.email = 'revoke@example.com'"
        )
    ).scalar_one()
    db_session.execute(
        text("UPDATE auth_sessions SET revoked_at = NOW() WHERE id = :i"),
        {"i": row},
    )
    db_session.commit()
    assert api_client.get("/api/auth/me").status_code == 401


# --- CSRF ----------------------------------------------------------------


def test_state_change_without_csrf_rejected(api_client, logged_in):
    logged_in()
    resp = api_client.post("/api/auth/logout")
    assert resp.status_code == 403


def test_state_change_with_wrong_csrf_rejected(api_client, logged_in):
    logged_in()
    resp = api_client.post("/api/auth/logout", headers={"X-CSRF-Token": "bad-token"})
    assert resp.status_code == 403


def test_csrf_from_another_session_rejected(api_client, make_api_client, make_user):
    """Two INDEPENDENT clients (both on taskdb_test): A must not honor B's token."""
    from app.auth.security import hash_password

    make_user("one@example.com", "pm", password_hash=hash_password("pw-one"))
    make_user("two@example.com", "pm", password_hash=hash_password("pw-two"))

    client_a = api_client
    resp_a = client_a.post(
        "/api/auth/login", json={"email": "one@example.com", "password": "pw-one"}
    )
    app_b, client_b, engine_b = make_api_client()
    resp_b = client_b.post(
        "/api/auth/login", json={"email": "two@example.com", "password": "pw-two"}
    )
    assert resp_a.status_code == 200 and resp_b.status_code == 200

    # A presents B's CSRF token → must fail (token is bound per-session).
    resp = client_a.post(
        "/api/auth/logout", headers={"X-CSRF-Token": resp_b.json()["csrf_token"]}
    )
    app_b.dependency_overrides.clear()
    engine_b.dispose()
    assert resp.status_code == 403


def test_csrf_token_distinct_from_session_credential(api_client, logged_in):
    csrf = logged_in(email="distinct@example.com")
    cookie = api_client.cookies.get(settings.SESSION_COOKIE_NAME)
    assert csrf != cookie


# --- rate limiting -------------------------------------------------------


def test_login_throttling_returns_429(api_client, make_user, inject_session_settings):
    from app.auth.security import hash_password

    rate_limit.configure_for_tests(max_attempts=3, window_seconds=60)
    make_user("throttle@example.com", "pm", password_hash=hash_password("pw"))

    codes = []
    for _ in range(4):
        resp = api_client.post(
            "/api/auth/login",
            json={"email": "throttle@example.com", "password": "definitely-wrong"},
        )
        codes.append(resp.status_code)

    assert codes[:3] == [401, 401, 401]
    assert codes[3] == 429
