"""Phase 4B Comment API tests — full approved matrix.

Runs against real MySQL (taskdb_test) via the isolated app fixtures.
Covers LIST / CREATE contracts: 401/403/404 separation, author security
(server-controlled user_id), strict input (400 vs 422), CSRF
enforcement, response sanitization, and the ABSENCE of any
update/delete/moderation endpoint.
"""

import pytest

from app.auth.security import hash_password


# --- fixtures ---------------------------------------------------------------


@pytest.fixture()
def pm_env(make_api_client, make_user):
    """Logged-in PM with its OWN client+cookie jar."""
    email = "pm4b@example.com"
    make_user(email, "pm", password_hash=hash_password("pw123456"))
    app, client, engine = make_api_client()
    resp = client.post(
        "/api/auth/login", json={"email": email, "password": "pw123456"}
    )
    assert resp.status_code == 200, resp.text
    uid = client.get("/api/auth/me").json()["user_id"]
    return client, resp.json()["csrf_token"], uid


@pytest.fixture()
def dev_env(pm_env, make_api_client, make_user):
    """Logged-in Developer with its OWN client+cookie jar."""
    email = "dev4b@example.com"
    make_user(email, "developer", password_hash=hash_password("pw123456"))
    app, client, engine = make_api_client()
    resp = client.post(
        "/api/auth/login", json={"email": email, "password": "pw123456"}
    )
    assert resp.status_code == 200, resp.text
    uid = client.get("/api/auth/me").json()["user_id"]
    return client, resp.json()["csrf_token"], uid


def _pm_creates_task(client, csrf, **overrides):
    payload = {
        "title": "Comment target",
        "priority": TaskPriorityValue.MEDIUM,
        "status": TaskStatusValue.TO_DO,
        **overrides,
    }
    resp = client.post("/api/tasks", json=payload, headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 201, resp.text
    return resp.json()


from app.models import TaskPriority as TaskPriorityValue  # noqa: E402
from app.models import TaskStatus as TaskStatusValue  # noqa: E402


# --- LIST ---------------------------------------------------------------------


def test_unauthenticated_list_401(api_client, pm_env):
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    anon = api_client
    assert anon.get(f"/api/tasks/{task['id']}/comments").status_code == 401


def test_pm_may_list_comments(pm_env):
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    resp = client.get(f"/api/tasks/{task['id']}/comments")
    assert resp.status_code == 200
    assert resp.json() == []


def test_developer_may_list_comments(dev_env, pm_env):
    pm_client, pm_csrf, _ = pm_env
    dev_client, _, _ = dev_env
    task = _pm_creates_task(pm_client, pm_csrf)
    resp = dev_client.get(f"/api/tasks/{task['id']}/comments")
    assert resp.status_code == 200
    assert resp.json() == []


def test_developer_lists_unassigned_and_foreign_tasks(
    dev_env, pm_env, db_session
):
    """No assignment requirement for viewing comments."""
    pm_client, pm_csrf, pm_uid = pm_env
    dev_client, dev_csrf, dev_uid = dev_env

    unassigned = _pm_creates_task(pm_client, pm_csrf, title="Unassigned t")
    foreign = _pm_creates_task(
        pm_client, pm_csrf, title="Foreign t", assignee_id=pm_uid
    )
    for t in (unassigned, foreign):
        resp = dev_client.get(f"/api/tasks/{t['id']}/comments")
        assert resp.status_code == 200


def test_missing_task_list_404_generic(pm_env):
    client, _, _ = pm_env
    resp = client.get("/api/tasks/99999/comments")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not found"}


# --- CREATE ---------------------------------------------------------------------


def test_unauthenticated_create_401(api_client, pm_env):
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    resp = api_client.post(
        f"/api/tasks/{task['id']}/comments", json={"content": "hi"}
    )
    assert resp.status_code == 401


def test_pm_may_create_comment(pm_env):
    client, csrf, uid = pm_env
    task = _pm_creates_task(client, csrf)
    resp = client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"content": "PM note"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["content"] == "PM note"
    assert body["user_id"] == uid
    assert body["task_id"] == task["id"]


def test_developer_may_create_comment_on_own_assigned_task(pm_env, dev_env):
    pm_client, pm_csrf, _ = pm_env
    dev_client, dev_csrf, dev_uid = dev_env
    task = _pm_creates_task(pm_client, pm_csrf, assignee_id=dev_uid)
    resp = dev_client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"content": "working on it"},
        headers={"X-CSRF-Token": dev_csrf},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["user_id"] == dev_uid


def test_developer_may_comment_on_another_users_task(pm_env, dev_env, db_session):
    from sqlalchemy import text

    pm_client, pm_csrf, _ = pm_env
    dev_client, dev_csrf, _ = dev_env
    other = db_session.execute(
        text("SELECT id FROM users WHERE email='other-dev-4b@example.com'")
    ).scalar()
    if other is None:
        from app.models import User

        db_session.add(
            User(email="other-dev-4b@example.com", role="developer",
                 password_hash="test-only-not-a-real-hash")
        )
        db_session.commit()
        other = int(db_session.execute(
            text("SELECT id FROM users WHERE email='other-dev-4b@example.com'")
        ).scalar_one())

    task = _pm_creates_task(pm_client, pm_csrf, assignee_id=other)
    resp = dev_client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"content": "unrelated but allowed"},
        headers={"X-CSRF-Token": dev_csrf},
    )
    assert resp.status_code == 201, resp.text


def test_developer_may_comment_on_unassigned_task(pm_env, dev_env):
    pm_client, pm_csrf, _ = pm_env
    dev_client, dev_csrf, _ = dev_env
    task = _pm_creates_task(pm_client, pm_csrf)  # unassigned
    resp = dev_client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"content": "free to comment"},
        headers={"X-CSRF-Token": dev_csrf},
    )
    assert resp.status_code == 201, resp.text


def test_missing_task_create_404(pm_env):
    client, csrf, _ = pm_env
    resp = client.post(
        "/api/tasks/99999/comments",
        json={"content": "ghost"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not found"}


def test_listing_after_creation_returns_both(pm_env, dev_env):
    pm_client, pm_csrf, _ = pm_env
    dev_client, dev_csrf, _ = dev_env
    task = _pm_creates_task(pm_client, pm_csrf)
    pm_client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"content": "first"},
        headers={"X-CSRF-Token": pm_csrf},
    )
    dev_client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"content": "second"},
        headers={"X-CSRF-Token": dev_csrf},
    )
    listed = pm_client.get(f"/api/tasks/{task['id']}/comments")
    assert [c["content"] for c in listed.json()] == ["first", "second"]
    assert {c["user_id"] for c in listed.json()} and len(listed.json()) == 2


# --- AUTHOR SECURITY ----------------------------------------------------------


@pytest.mark.parametrize("smuggled", [
    {"user_id": 999},
    {"task_id": 999},
    {"author_id": 999},
    {"role": "pm"},
    {"created_at": "1999-01-01T00:00:00"},
])
def test_client_cannot_supply_identity_fields_400(pm_env, smuggled):
    client, csrf, uid = pm_env
    task = _pm_creates_task(client, csrf)
    resp = client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"content": "hello", **smuggled},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 400
    # Spoofed values never persisted anywhere.
    listing = client.get(f"/api/tasks/{task['id']}/comments")
    assert all(c["user_id"] == uid for c in listing.json())
    spoofed_uid = smuggled.get("user_id")
    if spoofed_uid is not None:
        assert str(spoofed_uid) not in resp.text


def test_persisted_author_is_authenticated_user(pm_env, dev_env):
    pm_client, pm_csrf, pm_uid = pm_env
    dev_client, dev_csrf, dev_uid = dev_env
    task = _pm_creates_task(pm_client, pm_csrf)
    pm_client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"content": "by pm"},
        headers={"X-CSRF-Token": pm_csrf},
    )
    dev_client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"content": "by dev"},
        headers={"X-CSRF-Token": dev_csrf},
    )
    authors = {
        c["content"]: c["user_id"]
        for c in pm_client.get(f"/api/tasks/{task['id']}/comments").json()
    }
    assert authors["by pm"] == pm_uid
    assert authors["by dev"] == dev_uid


# --- VALIDATION ------------------------------------------------------------------


def test_content_required_422(pm_env):
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    resp = client.post(
        f"/api/tasks/{task['id']}/comments",
        json={},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


def test_content_null_rejected_before_db_422(pm_env):
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    resp = client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"content": None},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422, resp.text
    # Nothing persisted.
    assert client.get(f"/api/tasks/{task['id']}/comments").json() == []


def test_no_arbitrary_length_limit_introduced(pm_env):
    """Long content is accepted; no invented minimum/maximum."""
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    long_text = "x" * 5000
    resp = client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"content": long_text},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 201, resp.text
    assert len(resp.json()["content"]) == 5000


# --- CSRF --------------------------------------------------------------------------


def test_post_without_csrf_denied(pm_env):
    client, _, _ = pm_env
    task = _pm_creates_task(client, pm_env[1])
    resp = client.post(
        f"/api/tasks/{task['id']}/comments", json={"content": "no token"}
    )
    assert resp.status_code == 403


def test_post_with_invalid_csrf_denied(pm_env):
    client, _, _ = pm_env
    task = _pm_creates_task(client, pm_env[1])
    resp = client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"content": "bad token"},
        headers={"X-CSRF-Token": "wrong-token"},
    )
    assert resp.status_code == 403


def test_get_does_not_require_csrf(pm_env):
    client, _, _ = pm_env
    task = _pm_creates_task(client, pm_env[1])
    assert client.get(f"/api/tasks/{task['id']}/comments").status_code == 200


# --- RESPONSE CONTRACT --------------------------------------------------------------


def test_response_exposes_only_approved_comment_fields(pm_env):
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    created = client.post(
        f"/api/tasks/{task['id']}/comments",
        json={"content": "shape check"},
        headers={"X-CSRF-Token": csrf},
    ).json()
    assert set(created.keys()) == {"id", "task_id", "user_id", "content", "created_at"}
    low = str(created).lower()
    for banned in ("password", "hash", "session", "token", "csrf", "digest", "role"):
        assert banned not in low, f"leaked: {banned}"


def test_no_update_delete_or_moderation_endpoints_exist(app_under_test=None):
    """Structural scope check against the production route table."""
    from app.main import create_app

    paths = sorted({getattr(r, "path", "") for r in create_app().routes})
    comment_paths = [p for p in paths if "comment" in p]
    assert comment_paths == [
        "/api/tasks/{task_id}/comments",
    ] or set(comment_paths) == {"/api/tasks/{task_id}/comments"}
    methods = set()
    for r in create_app().routes:
        if getattr(r, "path", "") == "/api/tasks/{task_id}/comments":
            methods |= {m.upper() for m in getattr(r, "methods", set())}
    assert methods <= {"GET", "POST"}
