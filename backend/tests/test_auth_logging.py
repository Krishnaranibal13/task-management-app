"""Security logging tests: secrets must never reach the logs."""

from app.core.config import settings


def test_security_events_do_not_leak_secrets(api_client, make_user, capsys):
    """Exercise login/logout paths and scan captured stdout for secrets."""
    from app.auth.security import hash_password

    password = "super-secret-password-value"
    make_user("logcheck@example.com", "pm", password_hash=hash_password(password))

    resp = api_client.post(
        "/api/auth/login", json={"email": "logcheck@example.com", "password": password}
    )
    assert resp.status_code == 200
    cookie = api_client.cookies.get(settings.SESSION_COOKIE_NAME)
    csrf = resp.json()["csrf_token"]

    out = api_client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert out.status_code == 200

    failed = api_client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "guess"}
    )
    assert failed.status_code == 401

    captured = capsys.readouterr().out

    # Secrets of any kind must never appear.
    assert password not in captured
    assert cookie is not None and cookie not in captured
    assert csrf not in captured
    # Request bodies (which contain passwords) are never dumped.
    assert "super-secret-password-value" not in captured
    # Security events ARE recorded — with generic reasons only.
    assert "[security] event=auth_success" in captured
    assert "[security] event=logout" in captured
    assert "reason=invalid_credentials" in captured
    # No account-existence signal in failure logs.
    assert "unknown_email" not in captured
    # Emails are never logged.
    assert "logcheck@example.com" not in captured
    assert "ghost@example.com" not in captured


def test_validation_error_never_echoes_password(api_client):
    """Malformed login request → 400 without echoing submitted input."""
    secret_attempt = "MY-PLAINTEXT-PASSWORD-ECHO-CHECK"
    resp = api_client.post(
        "/api/auth/login",
        json={
            "email": "someone@example.com",
            "password": secret_attempt,
            "totally_unknown_field": "x",
        },
    )
    assert resp.status_code == 400
    body = resp.text
    assert secret_attempt not in body
    assert "someone@example.com" not in body
    assert "totally_unknown_field" not in body.lower() or "loc" in body


def test_unconfigured_session_lifetime_fails_closed(
    db_session, make_user, inject_session_settings, make_api_client
):
    """No invented fallback lifetime: unset lifetime → clear server-side
    configuration failure, NO session row created, nothing sensitive in
    the client-visible error."""
    from app.auth.security import hash_password

    restore = None
    try:
        make_user("nolf@example.com", "pm", password_hash=hash_password("pw123456"))
        # Client is created with the normal test-only lifetime; we then
        # strip it to simulate a misconfigured deployment.
        # raise_server_exceptions=False so the RuntimeError becomes HTTP 500.
        app, raw_client, test_engine = make_api_client(
            raise_server_exceptions=False
        )
        restore = inject_session_settings(SESSION_LIFETIME_SECONDS=None)
        resp = raw_client.post(
            "/api/auth/login",
            json={"email": "nolf@example.com", "password": "pw123456"},
        )
        assert resp.status_code == 500
        # Configuration internals must not be exposed to the client.
        assert "SESSION_LIFETIME_SECONDS" not in resp.text
        assert "must be set to a positive integer" not in resp.text
        # And critically: NO session was created FOR THIS USER.
        count = db_session.execute(
            __import__("sqlalchemy").text(
                "SELECT COUNT(*) FROM auth_sessions s JOIN users u "
                "ON u.id = s.user_id WHERE u.email = 'nolf@example.com'"
            )
        ).scalar_one()
        assert int(count) == 0
        app.dependency_overrides.clear()
        test_engine.dispose()
    finally:
        restore()


def test_negative_session_lifetime_fails_closed(inject_session_settings):
    """Non-positive lifetimes are equally rejected."""
    import pytest as _pytest

    from app.auth import session_service

    restore = inject_session_settings(SESSION_LIFETIME_SECONDS=-5)
    try:
        with _pytest.raises(RuntimeError):
            session_service._configured_lifetime_seconds()
    finally:
        restore()
