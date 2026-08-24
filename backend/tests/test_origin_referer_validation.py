"""SEC-MED-01 focused tests — centralized Origin/Referer defense-in-depth.

Proves, against real MySQL (taskdb_test):

  A. trusted Origin + valid CSRF  -> mutation reaches business behavior
  B. untrusted Origin + valid CSRF -> 403 (fail closed)
  C. trusted Referer when Origin absent -> accepted
  D. untrusted Referer when Origin absent -> 403
  E. malformed Referer -> 403
  F. missing-CSRF rejection unchanged (synchronizer check NOT weakened)
  G. invalid-CSRF rejection unchanged
  H. Developer /status endpoint protected
  I. Comment POST protected
  J. Logout protected (and fail-closed BEFORE revocation)
  K. Task create/update/delete protected
  L. Safe GET endpoints unaffected
  M. No credentials/tokens/header values in logs or error bodies

plus normalization guarantees: exact matching (no substring/suffix),
scheme/port sensitivity, default-port equivalence, Origin-over-Referer
precedence, opaque 'null' rejection, and the strictly validated
same-origin Host fallback.
"""

import pytest

from app.auth.security import hash_password
from app.core.config import settings

# Authoritative allowlist shape (same variable the CORS wiring consumes).
TRUSTED_ALLOWLIST = "http://localhost:3000,http://127.0.0.1:3000"
TRUSTED_ORIGIN = "http://localhost:3000"
OTHER_TRUSTED_ORIGIN = "http://127.0.0.1:3000"
EVIL_ORIGIN = "https://evil.example.net"
EVIL_REFERER = "https://evil.example.net/projects/board"

_TASK_PAYLOAD = {
    "title": "Origin security probe",
    "priority": "high",
    "status": "to_do",
}


class _Allowlist:
    """Context manager toggling the SINGLE authoritative origin allowlist."""

    def __init__(self, raw: str | None):
        self.raw = raw
        self._saved: str | None = None

    def __enter__(self) -> "_Allowlist":
        self._saved = settings.CORS_ALLOWED_ORIGINS_RAW
        if self.raw is not None:
            settings.CORS_ALLOWED_ORIGINS_RAW = self.raw
        return self

    def __exit__(self, *exc) -> bool:
        settings.CORS_ALLOWED_ORIGINS_RAW = self._saved
        return False


def allowlist(raw: str | None = TRUSTED_ALLOWLIST) -> _Allowlist:
    return _Allowlist(raw)


# --- fixtures ----------------------------------------------------------------


@pytest.fixture()
def pm_env(make_api_client, make_user):
    """Logged-in PM whose whole lifecycle runs under the trusted allowlist.

    Yields (client, csrf_token); configuration restored at teardown.
    """
    with allowlist():
        make_user(
            "pmsec@example.com", "pm", password_hash=hash_password("pw123456")
        )
        app, client, engine = make_api_client()
        resp = client.post(
            "/api/auth/login",
            json={"email": "pmsec@example.com", "password": "pw123456"},
        )
        assert resp.status_code == 200, resp.text
        yield client, resp.json()["csrf_token"]
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture()
def dev_client(pm_env, make_api_client, make_user):
    """Logged-in Developer with its OWN cookie jar (same allowlist posture).

    Yields (client, csrf_token, app, engine) so the test controls cleanup.
    """
    with allowlist():
        make_user(
            "devsec@example.com",
            "developer",
            password_hash=hash_password("pw123456"),
        )
        app, client, engine = make_api_client()
        resp = client.post(
            "/api/auth/login",
            json={"email": "devsec@example.com", "password": "pw123456"},
        )
        assert resp.status_code == 200, resp.text
        yield client, resp.json()["csrf_token"], app, engine
        app.dependency_overrides.clear()
        engine.dispose()


def _create_task(client, csrf, **overrides) -> int:
    payload = {**_TASK_PAYLOAD, **overrides}
    resp = client.post(
        "/api/tasks",
        json=payload,
        headers={"X-CSRF-Token": csrf, "Origin": TRUSTED_ORIGIN},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# --- A: trusted Origin + valid CSRF reaches business behavior ----------------


def test_a_trusted_origin_valid_csrf_mutation_executes(pm_env):
    client, csrf = pm_env
    resp = client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={"X-CSRF-Token": csrf, "Origin": TRUSTED_ORIGIN},
    )
    assert resp.status_code == 201, resp.text
    task_id = resp.json()["id"]
    # Business behavior really happened: the row exists and is readable.
    fetched = client.get(f"/api/tasks/{task_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == _TASK_PAYLOAD["title"]
    # Second trusted origin from the SAME allowlist is equally valid.
    resp2 = client.patch(
        f"/api/tasks/{task_id}",
        json={"description": "updated via other trusted origin"},
        headers={"X-CSRF-Token": csrf, "Origin": OTHER_TRUSTED_ORIGIN},
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["description"] == "updated via other trusted origin"


def test_a_trusted_origin_case_insensitive_host_matches(pm_env):
    """Normalization: scheme/host case differences converge before compare."""
    client, csrf = pm_env
    resp = client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={"X-CSRF-Token": csrf, "Origin": "http://LOCALHOST:3000"},
    )
    assert resp.status_code == 201, resp.text


def test_a_default_port_explicit_vs_elided_is_equivalent(make_api_client, make_user):
    """An allowlist entry written with the scheme-default port and a
    presented Origin without it normalize to the SAME origin."""
    with allowlist("https://app.example.com:443"):
        make_user(
            "pmport@example.com", "pm", password_hash=hash_password("pw123456")
        )
        app, client, engine = make_api_client()
        try:
            resp = client.post(
                "/api/auth/login",
                json={"email": "pmport@example.com", "password": "pw123456"},
            )
            assert resp.status_code == 200, resp.text
            csrf = resp.json()["csrf_token"]
            created = client.post(
                "/api/tasks",
                json=_TASK_PAYLOAD,
                headers={"X-CSRF-Token": csrf, "Origin": "https://app.example.com"},
            )
            assert created.status_code == 201, created.text
        finally:
            app.dependency_overrides.clear()
            engine.dispose()


# --- B: untrusted Origin rejected despite valid CSRF -------------------------


def test_b_untrusted_origin_rejected_403(pm_env):
    client, csrf = pm_env
    resp = client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={"X-CSRF-Token": csrf, "Origin": EVIL_ORIGIN},
    )
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Forbidden"}
    # Offending value is never reflected.
    assert EVIL_ORIGIN not in resp.text
    # Nothing was created.
    assert client.get("/api/tasks").json() == []


def test_b_exact_matching_no_suffix_lookalike(pm_env):
    """Substring/suffix tricks can never smuggle an origin through."""
    client, csrf = pm_env
    for hostile in (
        "http://localhost:3000.evil.com",     # suffix on trusted host
        "http://localhost:3001",              # adjacent port
        "https://localhost:3000",             # wrong scheme, right port
        "http://localhost:3000.attacker.io",  # dotted suffix
    ):
        resp = client.post(
            "/api/tasks",
            json=_TASK_PAYLOAD,
            headers={"X-CSRF-Token": csrf, "Origin": hostile},
        )
        assert resp.status_code == 403, hostile
    assert client.get("/api/tasks").json() == []


def test_b_opaque_null_origin_rejected(pm_env):
    client, csrf = pm_env
    resp = client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={"X-CSRF-Token": csrf, "Origin": "null"},
    )
    assert resp.status_code == 403


def test_b_malformed_origin_rejected(pm_env):
    client, csrf = pm_env
    for hostile in (
        "not-an-origin",
        "http://user:pass@localhost:3000",  # credentials embedded
        "ftp://localhost:3000",             # non-web scheme
        "http://localhost:3000/path",       # Origin is a bare origin only
    ):
        resp = client.post(
            "/api/tasks",
            json=_TASK_PAYLOAD,
            headers={"X-CSRF-Token": csrf, "Origin": hostile},
        )
        assert resp.status_code == 403, hostile


# --- C/D/E: Referer handling when Origin absent ------------------------------


def test_c_trusted_referer_accepted_when_origin_absent(pm_env):
    client, csrf = pm_env
    resp = client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={
            "X-CSRF-Token": csrf,
            "Referer": f"{TRUSTED_ORIGIN}/projects/board?tab=all#column-2",
        },
    )
    assert resp.status_code == 201, resp.text
    # Path/query/fragment were discarded: ONLY the origin was compared.


def test_d_untrusted_referer_rejected_403(pm_env):
    client, csrf = pm_env
    resp = client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={"X-CSRF-Token": csrf, "Referer": EVIL_REFERER},
    )
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Forbidden"}
    # Full URL is never reflected either.
    assert EVIL_REFERER not in resp.text
    assert client.get("/api/tasks").json() == []


def test_e_malformed_referer_rejected_403(pm_env):
    client, csrf = pm_env
    for hostile in (
        "not-a-url-at-all",
        "/relative/only/path",
        "file:///C:/Windows/system32/config",
        "javascript:alert(document.domain)",
        "data:text/html;base64,PGh0bWw+",
    ):
        resp = client.post(
            "/api/tasks",
            json=_TASK_PAYLOAD,
            headers={"X-CSRF-Token": csrf, "Referer": hostile},
        )
        assert resp.status_code == 403, hostile
    assert client.get("/api/tasks").json() == []


def test_origin_header_takes_precedence_over_referer(pm_env):
    """When Origin is present it governs; a hostile Referer cannot poison
    a trusted-Origin request, and a trusted Referer cannot rescue an
    untrusted Origin."""
    client, csrf = pm_env
    good_origin_bad_referer = client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={
            "X-CSRF-Token": csrf,
            "Origin": TRUSTED_ORIGIN,
            "Referer": EVIL_REFERER,
        },
    )
    assert good_origin_bad_referer.status_code == 201

    bad_origin_good_referer = client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={
            "X-CSRF-Token": csrf,
            "Origin": EVIL_ORIGIN,
            "Referer": f"{TRUSTED_ORIGIN}/safe/looking/page",
        },
    )
    assert bad_origin_good_referer.status_code == 403


# --- F/G: the primary synchronizer-token control is untouched ----------------


def test_f_missing_csrf_still_rejected_without_any_headers(pm_env):
    client, _ = pm_env
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "CSRF validation failed"


def test_g_invalid_csrf_still_rejected_without_any_headers(pm_env):
    client, _ = pm_env
    resp = client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={"X-CSRF-Token": "deliberately-wrong-token"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "CSRF validation failed"
    assert client.get("/api/tasks").json() == []


def test_cross_session_token_binding_unchanged(pm_env, make_api_client, make_user):
    """Defense-in-depth did not alter token-per-session binding."""
    client_a, csrf_a = pm_env
    with allowlist():
        make_user(
            "othersec@example.com", "pm", password_hash=hash_password("pw-two-34")
        )
        app_b, client_b, engine_b = make_api_client()
        try:
            resp_b = client_b.post(
                "/api/auth/login",
                json={"email": "othersec@example.com", "password": "pw-two-34"},
            )
            assert resp_b.status_code == 200
            csrf_b = resp_b.json()["csrf_token"]
            # A presents B's token, no Origin headers at all → token check
            # alone rejects (unchanged behavior).
            resp = client_a.post(
                "/api/auth/logout", headers={"X-CSRF-Token": csrf_b}
            )
            assert resp.status_code == 403
        finally:
            app_b.dependency_overrides.clear()
            engine_b.dispose()
    del csrf_a, client_a


# --- H: Developer /status endpoint --------------------------------------------


def test_h_developer_status_endpoint_origin_protected(pm_env, dev_client):
    client, pm_csrf = pm_env
    dev, dev_csrf, _app, _engine = dev_client
    dev_id = dev.get("/api/auth/me").json()["user_id"]
    task_id = _create_task(client, pm_csrf, assignee_id=dev_id)

    # Untrusted Origin + otherwise valid request → 403, status unchanged.
    denied = dev.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "in_progress"},
        headers={"X-CSRF-Token": dev_csrf, "Origin": EVIL_ORIGIN},
    )
    assert denied.status_code == 403
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "to_do"

    # Trusted Origin → the approved business action proceeds.
    allowed = dev.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "in_progress"},
        headers={"X-CSRF-Token": dev_csrf, "Origin": TRUSTED_ORIGIN},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["status"] == "in_progress"

    # Untrusted Referer (no Origin) → equally denied.
    denied_ref = dev.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "review"},
        headers={"X-CSRF-Token": dev_csrf, "Referer": EVIL_REFERER},
    )
    assert denied_ref.status_code == 403


# --- I: Comment POST -----------------------------------------------------------


def test_i_comment_post_origin_protected(pm_env):
    client, csrf = pm_env
    task_id = _create_task(client, csrf)

    denied = client.post(
        f"/api/tasks/{task_id}/comments",
        json={"content": "hostile origin comment"},
        headers={"X-CSRF-Token": csrf, "Origin": EVIL_ORIGIN},
    )
    assert denied.status_code == 403

    denied_ref = client.post(
        f"/api/tasks/{task_id}/comments",
        json={"content": "hostile referer comment"},
        headers={"X-CSRF-Token": csrf, "Referer": EVIL_REFERER},
    )
    assert denied_ref.status_code == 403
    assert client.get(f"/api/tasks/{task_id}/comments").json() == []

    allowed = client.post(
        f"/api/tasks/{task_id}/comments",
        json={"content": "legitimate comment"},
        headers={
            "X-CSRF-Token": csrf,
            "Referer": f"{TRUSTED_ORIGIN}/tasks/{task_id}",
        },
    )
    assert allowed.status_code == 201, allowed.text
    comments = client.get(f"/api/tasks/{task_id}/comments").json()
    assert [c["content"] for c in comments] == ["legitimate comment"]


# --- J: Logout ------------------------------------------------------------------


def test_j_logout_origin_protected_and_fail_closed_before_revocation(pm_env):
    client, csrf = pm_env
    denied = client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": csrf, "Origin": EVIL_ORIGIN},
    )
    assert denied.status_code == 403
    # Rejection happened BEFORE any state change: session still active.
    assert client.get("/api/auth/me").status_code == 200

    allowed = client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": csrf, "Origin": TRUSTED_ORIGIN},
    )
    assert allowed.status_code == 200
    # Now the approved logout semantics completed end-to-end.
    assert client.get("/api/auth/me").status_code == 401


# --- K: Task create/update/delete ------------------------------------------------


def test_k_task_mutations_origin_protected_end_to_end(pm_env):
    client, csrf = pm_env
    task_id = _create_task(client, csrf)

    # General PATCH denied on untrusted Origin...
    patch_denied = client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "attacker rename"},
        headers={"X-CSRF-Token": csrf, "Origin": EVIL_ORIGIN},
    )
    assert patch_denied.status_code == 403
    # ...and on untrusted Referer.
    patch_denied_ref = client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "attacker rename 2"},
        headers={"X-CSRF-Token": csrf, "Referer": EVIL_REFERER},
    )
    assert patch_denied_ref.status_code == 403

    # DELETE denied on untrusted Origin.
    delete_denied = client.delete(
        f"/api/tasks/{task_id}", headers={"X-CSRF-Token": csrf, "Origin": EVIL_ORIGIN}
    )
    assert delete_denied.status_code == 403

    # CREATE denied on untrusted Origin.
    create_denied = client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={"X-CSRF-Token": csrf, "Origin": EVIL_ORIGIN},
    )
    assert create_denied.status_code == 403

    # State untouched by every denial.
    current = client.get(f"/api/tasks/{task_id}")
    assert current.status_code == 200
    assert current.json()["title"] == _TASK_PAYLOAD["title"]

    # The very same operations succeed under the trusted origin.
    assert (
        client.patch(
            f"/api/tasks/{task_id}",
            json={"title": "renamed by owner"},
            headers={"X-CSRF-Token": csrf, "Origin": TRUSTED_ORIGIN},
        ).status_code
        == 200
    )
    extra_id = _create_task(client, csrf)  # trusted create
    assert (
        client.delete(
            f"/api/tasks/{extra_id}",
            headers={"X-CSRF-Token": csrf, "Origin": OTHER_TRUSTED_ORIGIN},
        ).status_code
        == 204
    )


# --- L: safe GET endpoints unaffected ---------------------------------------------


def test_l_safe_gets_ignore_origin_headers_under_allowlist(pm_env):
    client, csrf = pm_env
    task_id = _create_task(client, csrf)
    hostile_headers = {"Origin": EVIL_ORIGIN, "Referer": EVIL_REFERER}

    assert client.get("/api/tasks", headers=hostile_headers).status_code == 200
    assert (
        client.get(f"/api/tasks/{task_id}", headers=hostile_headers).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/tasks/{task_id}/comments", headers=hostile_headers
        ).status_code
        == 200
    )
    assert client.get("/api/users", headers=hostile_headers).status_code == 200
    assert client.get("/api/health", headers=hostile_headers).status_code == 200

    # Authenticated SAFE bootstrap endpoint also unaffected (do this LAST:
    # it rotates this session's CSRF token by design).
    bootstrap = client.get("/api/auth/csrf", headers=hostile_headers)
    assert bootstrap.status_code == 200
    rotated = bootstrap.json()["csrf_token"]
    assert rotated != csrf
    # And the rotated token is immediately usable for a mutation.
    assert (
        client.post(
            "/api/tasks",
            json=_TASK_PAYLOAD,
            headers={"X-CSRF-Token": rotated, "Origin": TRUSTED_ORIGIN},
        ).status_code
        == 201
    )


def test_l_safe_gets_unaffected_without_allowlist(api_client, make_user):
    """Same-origin posture (empty allowlist): hostile Origin headers on
    SAFE methods change nothing."""
    from app.auth.security import hash_password

    make_user("getsafe@example.com", "pm", password_hash=hash_password("pw123456"))
    resp = api_client.post(
        "/api/auth/login", json={"email": "getsafe@example.com", "password": "pw123456"}
    )
    assert resp.status_code == 200
    hostile = {"Origin": EVIL_ORIGIN, "Referer": EVIL_REFERER}
    assert api_client.get("/api/tasks", headers=hostile).status_code == 200
    assert api_client.get("/api/auth/me", headers=hostile).status_code == 200
    assert api_client.get("/api/users", headers=hostile).status_code == 200


# --- same-origin Host fallback (no allowlist configured) ---------------------------


def test_fallback_accepts_own_host_and_rejects_foreign(api_client, make_user):
    """Zero-config posture: the request's own validated Host is the single
    acceptable self-origin; everything else fails closed."""
    from app.auth.security import hash_password

    make_user(
        "fallback@example.com", "pm", password_hash=hash_password("pw123456")
    )
    resp = api_client.post(
        "/api/auth/login",
        json={"email": "fallback@example.com", "password": "pw123456"},
    )
    assert resp.status_code == 200
    csrf = resp.json()["csrf_token"]

    own = api_client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={"X-CSRF-Token": csrf, "Origin": "http://testserver"},
    )
    assert own.status_code == 201, own.text

    for hostile in (EVIL_ORIGIN, "http://testserver.evil.com", "null"):
        denied = api_client.post(
            "/api/tasks",
            json=_TASK_PAYLOAD,
            headers={"X-CSRF-Token": csrf, "Origin": hostile},
        )
        assert denied.status_code == 403, hostile


def test_fallback_referer_own_host_accepted_foreign_rejected(api_client, make_user):
    from app.auth.security import hash_password

    make_user(
        "fbref@example.com", "pm", password_hash=hash_password("pw123456")
    )
    resp = api_client.post(
        "/api/auth/login",
        json={"email": "fbref@example.com", "password": "pw123456"},
    )
    assert resp.status_code == 200
    csrf = resp.json()["csrf_token"]

    own = api_client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={"X-CSRF-Token": csrf, "Referer": "http://testserver/board"},
    )
    assert own.status_code == 201, own.text

    denied = api_client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={"X-CSRF-Token": csrf, "Referer": EVIL_REFERER},
    )
    assert denied.status_code == 403


def test_fallback_invalid_host_fails_closed(api_client, make_user):
    """Tampered/unparseable Host under the zero-config posture → generic
    403 rather than a silent accept or a 500."""
    from app.auth.security import hash_password

    make_user("badhost@example.com", "pm", password_hash=hash_password("pw123456"))
    resp = api_client.post(
        "/api/auth/login",
        json={"email": "badhost@example.com", "password": "pw123456"},
    )
    assert resp.status_code == 200
    csrf = resp.json()["csrf_token"]

    denied = api_client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={
            "X-CSRF-Token": csrf,
            "Origin": "http://testserver",
            "Host": "testserver:99999",  # out-of-range port → unparseable
        },
    )
    assert denied.status_code == 403
    assert denied.json() == {"detail": "Forbidden"}


# --- M: hygiene — no secrets or header values in logs/errors ------------------------


def test_m_no_credentials_or_header_values_in_logs_or_error_bodies(
    pm_env, capsys
):
    client, csrf = pm_env
    cookie = client.cookies.get(settings.SESSION_COOKIE_NAME)
    assert cookie  # a session credential is actually in play

    denied = client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={"X-CSRF-Token": csrf, "Origin": EVIL_ORIGIN, "Referer": EVIL_REFERER},
    )
    assert denied.status_code == 403
    body = denied.text

    malformed = client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={"X-CSRF-Token": csrf, "Referer": "totally-malformed%%$$"},
    )
    assert malformed.status_code == 403

    client.post(
        "/api/auth/logout", headers={"X-CSRF-Token": csrf, "Origin": EVIL_ORIGIN}
    )

    # An APPROVED mutation (trusted origin) still executes normally after
    # the defense-in-depth layer was added...
    approved = client.post(
        "/api/tasks",
        json=_TASK_PAYLOAD,
        headers={"X-CSRF-Token": csrf, "Origin": TRUSTED_ORIGIN},
    )
    assert approved.status_code == 201

    # ...and an APPROVED logout still emits the normal security event.
    out = client.post(
        "/api/auth/logout", headers={"X-CSRF-Token": csrf, "Origin": TRUSTED_ORIGIN}
    )
    assert out.status_code == 200
    assert client.get("/api/auth/me").status_code == 401

    captured = capsys.readouterr().out
    # Session credential, CSRF token, and presented header values never leak.
    for secret in (
        cookie,
        csrf,
        EVIL_ORIGIN,
        EVIL_REFERER,
        "totally-malformed%%$$",
        _TASK_PAYLOAD["title"],
    ):
        assert secret not in captured
    # Normal security events ARE still emitted for authorized activity;
    # denial paths add NO new log surface of their own.
    assert "[security] event=logout" in captured
    # Error bodies stay sanitized/generic.
    for secret in (csrf, cookie, EVIL_ORIGIN, EVIL_REFERER):
        assert secret not in denied.text
    assert denied.json() == {"detail": "Forbidden"}
