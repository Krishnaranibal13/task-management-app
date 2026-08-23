"""Phase 4A Task API tests — full approved matrix.

Runs against real MySQL (taskdb_test) via the isolated app fixtures.
Covers VIEW / CREATE / GENERAL PATCH / STATUS PATCH / ASSIGNMENT /
DELETE contracts including 401/403/404 separation, CSRF enforcement,
strict-input 400s, transition-freedom, and response sanitization.
"""

import datetime

import pytest
from sqlalchemy import text

from app.auth.security import hash_password
from app.models import TaskPriority, TaskStatus

# Approved persisted enum values (authoritative from Phase 2).
TODO = TaskStatus.TO_DO.value          # "to_do"
IN_PROGRESS = TaskStatus.IN_PROGRESS.value
REVIEW = TaskStatus.REVIEW.value
DONE = TaskStatus.DONE.value
LOW = TaskPriority.LOW.value
MEDIUM = TaskPriority.MEDIUM.value
HIGH = TaskPriority.HIGH.value


# --- helpers ---------------------------------------------------------------


@pytest.fixture()
def pm_env(make_api_client, make_user):
    """Logged-in PM with its OWN client+cookie jar.

    (client, csrf_token, user_id). Separate clients per role prevent the
    second login from overwriting the first session's cookie.
    """
    email = "pm4a@example.com"
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
    email = "dev4a@example.com"
    make_user(email, "developer", password_hash=hash_password("pw123456"))
    app, client, engine = make_api_client()
    resp = client.post(
        "/api/auth/login", json={"email": email, "password": "pw123456"}
    )
    assert resp.status_code == 200, resp.text
    uid = client.get("/api/auth/me").json()["user_id"]
    return client, resp.json()["csrf_token"], uid


def _second_dev_id(db_session, email="dev4a@example.com"):
    """Id of an existing developer row, creating it if absent.

    Several tests reference a second/third user; creation here keeps
    them self-contained regardless of execution order.
    """
    from app.models import User

    row = db_session.execute(
        text("SELECT id FROM users WHERE email = :e"), {"e": email}
    ).scalar()
    if row is not None:
        return int(row)
    db_session.add(
        User(email=email, role="developer",
             password_hash="test-only-not-a-real-hash")
    )
    db_session.commit()
    return int(
        db_session.execute(
            text("SELECT id FROM users WHERE email = :e"), {"e": email}
        ).scalar_one()
    )


def _uid(env) -> int:
    """Extract the authenticated user id from a (client, csrf, uid) env."""
    return env[2]


def _pm_creates_task(client, csrf, **overrides):
    payload = {
        "title": "Seed task",
        "priority": MEDIUM,
        "status": TODO,
        **overrides,
    }
    resp = client.post(
        "/api/tasks", json=payload, headers={"X-CSRF-Token": csrf}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _seed_task_db(db_session, **overrides):
    """Insert a task row directly (for view/patch targets)."""
    params = {
        "title": "DB task",
        "priority": TaskPriority.MEDIUM,
        "status": TaskStatus.TO_DO,
    }
    params.update(overrides)
    from app.models import Task

    t = Task(**params)
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


# --- VIEW --------------------------------------------------------------------


def test_unauthenticated_list_401(api_client):
    assert api_client.get("/api/tasks").status_code == 401


def test_unauthenticated_detail_401(api_client):
    assert api_client.get("/api/tasks/1").status_code == 401


def test_pm_may_list_and_view(pm_env, db_session):
    client, _, _ = pm_env
    seeded = _seed_task_db(db_session, title="Visible A")
    _seed_task_db(db_session, title="Visible B")

    listing = client.get("/api/tasks")
    assert listing.status_code == 200
    titles = [t["title"] for t in listing.json()]
    assert set(titles) >= {"Visible A", "Visible B"}

    detail = client.get(f"/api/tasks/{seeded.id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Visible A"
    assert detail.json()["id"] == seeded.id


def test_developer_may_list_and_view(dev_env, db_session):
    client, _, _ = dev_env
    seeded = _seed_task_db(db_session, title="Dev visible")

    assert client.get("/api/tasks").status_code == 200
    detail = client.get(f"/api/tasks/{seeded.id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Dev visible"


def test_missing_task_detail_404(pm_env):
    client, _, _ = pm_env
    resp = client.get("/api/tasks/99999")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not found"}


def test_task_response_excludes_security_state(pm_env):
    """Response schema structurally excludes ORM/security internals."""
    client, csrf, _ = pm_env
    body = _pm_creates_task(client, csrf)
    low = str(body).lower()
    for banned in (
        "password_hash",
        "session",
        "token",
        "csrf",
        "digest",
        "created_at",
        "updated_at",
    ):
        assert banned not in low, f"leaked: {banned}"


# --- CREATE ------------------------------------------------------------------


def test_pm_may_create_minimal(pm_env):
    client, csrf, _ = pm_env
    body = _pm_creates_task(client, csrf)
    assert body["title"] == "Seed task"
    assert body["description"] is None
    assert body["assignee_id"] is None
    assert body["priority"] == MEDIUM
    assert body["status"] == TODO
    assert body["due_date"] is None
    assert isinstance(body["id"], int)


def test_pm_may_create_full_payload(pm_env, db_session):
    client, csrf, pm_id = pm_env
    body = _pm_creates_task(
        client,
        csrf,
        description="Full fields",
        assignee_id=_second_dev_id(db_session),
        priority=HIGH,
        status=IN_PROGRESS,
        due_date="2026-12-31",
    )
    assert body["description"] == "Full fields"
    assert body["assignee_id"] == _second_dev_id(db_session)
    assert body["priority"] == HIGH
    assert body["status"] == IN_PROGRESS
    assert body["due_date"] == "2026-12-31"


def test_developer_create_403(dev_env):
    client, csrf, _ = dev_env
    resp = client.post(
        "/api/tasks",
        json={"title": "Nope", "priority": LOW, "status": TODO},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Forbidden"}


def test_unauthenticated_create_401(api_client):
    resp = api_client.post(
        "/api/tasks", json={"title": "x", "priority": LOW, "status": TODO}
    )
    assert resp.status_code == 401


def test_create_missing_csrf_denied(pm_env):
    client, _, _ = pm_env
    resp = client.post(
        "/api/tasks", json={"title": "x", "priority": LOW, "status": TODO}
    )
    assert resp.status_code == 403  # Phase 3A CSRF contract


def test_create_invalid_csrf_denied(pm_env):
    client, _, _ = pm_env
    resp = client.post(
        "/api/tasks",
        json={"title": "x", "priority": LOW, "status": TODO},
        headers={"X-CSRF-Token": "wrong-token-value"},
    )
    assert resp.status_code == 403


def test_create_unknown_field_400(pm_env):
    client, csrf, _ = pm_env
    resp = client.post(
        "/api/tasks",
        json={
            "title": "x",
            "priority": LOW,
            "status": TODO,
            "labels": ["unapproved"],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 400
    # Sanitized: field NAME may appear as location; submitted VALUES may not.
    assert "unapproved" not in resp.text


def test_create_required_fields_enforced(pm_env):
    client, csrf, _ = pm_env
    for missing in ("title", "priority", "status"):
        payload = {
            "title": "x",
            "priority": LOW,
            "status": TODO,
        }
        del payload[missing]
        resp = client.post(
            "/api/tasks", json=payload, headers={"X-CSRF-Token": csrf}
        )
        # Unrelated validation errors keep normal FastAPI semantics (422).
        assert resp.status_code == 422, f"{missing}: {resp.status_code}"
        assert "x" not in resp.text or missing != "title"


def test_create_invalid_status_value_rejected(pm_env):
    client, csrf, _ = pm_env
    resp = client.post(
        "/api/tasks",
        json={"title": "x", "priority": LOW, "status": "banana"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422
    assert "banana" not in resp.text


def test_create_server_managed_fields_are_unknown_fields(pm_env):
    client, csrf, _ = pm_env
    for smuggled in (
        {"id": 77},
        {"created_at": "2020-01-01T00:00:00"},
        {"updated_at": "2020-01-01T00:00:00"},
        {"role": "pm"},
        {"creator_id": 5},
    ):
        resp = client.post(
            "/api/tasks",
            json={"title": "x", "priority": LOW, "status": TODO, **smuggled},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400, smuggled


def test_create_nonexistent_assignee_400_sanitized(pm_env):
    client, csrf, _ = pm_env
    marker = 987654
    resp = client.post(
        "/api/tasks",
        json={
            "title": "x",
            "priority": LOW,
            "status": TODO,
            "assignee_id": marker,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 400
    assert str(marker) not in resp.text  # no ID echo


# --- GENERAL PATCH ------------------------------------------------------------


def test_pm_may_update_approved_fields(pm_env):
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    resp = client.patch(
        f"/api/tasks/{task['id']}",
        json={
            "title": "Renamed",
            "description": "New desc",
            "priority": HIGH,
            "due_date": "2027-01-15",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "Renamed"
    assert body["description"] == "New desc"
    assert body["priority"] == HIGH
    assert body["due_date"] == "2027-01-15"
    assert body["status"] == TODO  # untouched field preserved


def test_developer_general_patch_403_even_status_only(dev_env):
    """Critical: developers can NEVER use the general endpoint — not even
    with a status-only payload."""
    client, csrf, _ = dev_env
    resp = client.patch(
        "/api/tasks/1",
        json={"status": DONE},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Forbidden"}


def test_developer_general_patch_403_for_title_too(dev_env):
    client, csrf, _ = dev_env
    resp = client.patch(
        "/api/tasks/1",
        json={"title": "hijack"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 403


def test_general_patch_unknown_field_400(pm_env):
    client, csrf, _ = pm_env
    resp = client.patch(
        "/api/tasks/1",
        json={"story_points": 5},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 400


def test_general_patch_cannot_mutate_managed_fields(pm_env):
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    original_id = task["id"]
    for smuggled in ({"id": 42}, {"created_at": "1999-01-01T00:00:00"}):
        resp = client.patch(
            f"/api/tasks/{original_id}",
            json=smuggled,
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400, smuggled
    assert client.get(f"/api/tasks/{original_id}").json()["id"] == original_id


def test_general_patch_missing_task_404(pm_env):
    client, csrf, _ = pm_env
    resp = client.patch(
        "/api/tasks/99999",
        json={"title": "ghost"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 404


def test_general_patch_unauthenticated_401(api_client):
    assert (
        api_client.patch("/api/tasks/1", json={"title": "x"}).status_code == 401
    )


# --- DEDICATED STATUS ENDPOINT --------------------------------------------------


def test_pm_status_update_any_assignee(pm_env, db_session):
    client, csrf, _ = pm_env
    assigned = _second_dev_id(db_session)
    for seed_assignee in (None, assigned):  # unassigned OR assigned
        if seed_assignee is None:
            task = _pm_creates_task(client, csrf)
        else:
            task = _pm_creates_task(client, csrf, assignee_id=seed_assignee)
        resp = client.patch(
            f"/api/tasks/{task['id']}/status",
            json={"status": REVIEW},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == REVIEW


def test_developer_status_on_own_assigned_task_allowed(
    pm_env, dev_env, db_session
):
    pm_client, pm_csrf, _ = pm_env
    dev_client, dev_csrf, dev_uid = dev_env
    task = _pm_creates_task(
        pm_client, pm_csrf, assignee_id=dev_uid
    )

    resp = dev_client.patch(
        f"/api/tasks/{task['id']}/status",
        json={"status": IN_PROGRESS},
        headers={"X-CSRF-Token": dev_csrf},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == IN_PROGRESS


def test_developer_status_on_others_task_403(pm_env, dev_env, db_session):
    pm_client, pm_csrf, pm_uid = pm_env
    dev_client, dev_csrf, dev_uid = dev_env
    # Task assigned to a DIFFERENT developer than the one attempting.
    other_dev = _second_dev_id(
        db_session, email="other-dev@example.com"
    )
    assert other_dev != dev_uid
    task = _pm_creates_task(pm_client, pm_csrf, assignee_id=other_dev)

    resp = dev_client.patch(
        f"/api/tasks/{task['id']}/status",
        json={"status": DONE},
        headers={"X-CSRF-Token": dev_csrf},
    )
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Forbidden"}
    # State unchanged.
    assert pm_client.get(f"/api/tasks/{task['id']}").json()["status"] == TODO


def test_developer_status_on_unassigned_task_403(pm_env, dev_env):
    pm_client, pm_csrf, _ = pm_env
    dev_client, dev_csrf, _ = dev_env
    task = _pm_creates_task(pm_client, pm_csrf)  # unassigned

    resp = dev_client.patch(
        f"/api/tasks/{task['id']}/status",
        json={"status": DONE},
        headers={"X-CSRF-Token": dev_csrf},
    )
    assert resp.status_code == 403


def test_status_endpoint_rejects_extra_fields_400(pm_env, dev_env):
    pm_client, pm_csrf, _ = pm_env
    dev_client, dev_csrf, dev_uid = dev_env
    task = _pm_creates_task(pm_client, pm_csrf, assignee_id=dev_uid)

    # Even an ASSIGNED developer cannot smuggle extra fields.
    resp = dev_client.patch(
        f"/api/tasks/{task['id']}/status",
        json={"status": DONE, "title": "smuggled"},
        headers={"X-CSRF-Token": dev_csrf},
    )
    assert resp.status_code == 400
    assert "smuggled" not in resp.text

    # ...nor priority, nor assignment claims.
    resp2 = dev_client.patch(
        f"/api/tasks/{task['id']}/status",
        json={"status": DONE, "assignee_id": dev_uid},
        headers={"X-CSRF-Token": dev_csrf},
    )
    assert resp2.status_code == 400


def test_status_endpoint_invalid_status_422(pm_env):
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    resp = client.patch(
        f"/api/tasks/{task['id']}/status",
        json={"status": "finished"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422
    assert "finished" not in resp.text


def test_status_endpoint_missing_body_field_422(pm_env):
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    resp = client.patch(
        f"/api/tasks/{task['id']}/status",
        json={},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (TODO, DONE),           # forward jump
        (DONE, TODO),           # backward
        (REVIEW, IN_PROGRESS),  # backward
        (IN_PROGRESS, REVIEW),  # forward
    ],
)
def test_no_transition_restrictions(pm_env, from_status, to_status):
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf, status=from_status)
    resp = client.patch(
        f"/api/tasks/{task['id']}/status",
        json={"status": to_status},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == to_status


def test_status_endpoint_missing_task_404(pm_env):
    client, csrf, _ = pm_env
    resp = client.patch(
        "/api/tasks/99999/status",
        json={"status": DONE},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 404


def test_status_endpoint_requires_csrf(pm_env):
    client, _, _ = pm_env
    task = _pm_creates_task(client, pm_env[1])
    resp = client.patch(f"/api/tasks/{task['id']}/status", json={"status": DONE})
    assert resp.status_code == 403


# --- ASSIGNMENT -------------------------------------------------------------------


def test_pm_assign_reassign_unassign(pm_env, db_session):
    client, csrf, _ = pm_env
    dev_a = _second_dev_id(db_session)
    dev_b = _second_dev_id(db_session, email="second-dev@example.com")

    task = _pm_creates_task(client, csrf)

    r1 = client.patch(
        f"/api/tasks/{task['id']}",
        json={"assignee_id": dev_a},
        headers={"X-CSRF-Token": csrf},
    )
    assert r1.status_code == 200 and r1.json()["assignee_id"] == dev_a

    r2 = client.patch(
        f"/api/tasks/{task['id']}",
        json={"assignee_id": dev_b},   # reassign
        headers={"X-CSRF-Token": csrf},
    )
    assert r2.status_code == 200 and r2.json()["assignee_id"] == dev_b

    r3 = client.patch(
        f"/api/tasks/{task['id']}",
        json={"assignee_id": None},    # unassign
        headers={"X-CSRF-Token": csrf},
    )
    assert r3.status_code == 200 and r3.json()["assignee_id"] is None


def test_developer_cannot_assign_or_reassign(pm_env, dev_env):
    pm_client, pm_csrf, _ = pm_env
    dev_client, dev_csrf, dev_uid = dev_env
    task = _pm_creates_task(pm_client, pm_csrf)

    resp = dev_client.patch(
        f"/api/tasks/{task['id']}",
        json={"assignee_id": dev_uid},
        headers={"X-CSRF-Token": dev_csrf},
    )
    assert resp.status_code == 403


def test_assign_nonexistent_user_400_both_endpoints(pm_env):
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    ghost = 555555

    r_create_style = client.patch(
        f"/api/tasks/{task['id']}",
        json={"assignee_id": ghost},
        headers={"X-CSRF-Token": csrf},
    )
    assert r_create_style.status_code == 400
    assert str(ghost) not in r_create_style.text

    r_post = client.post(
        "/api/tasks",
        json={
            "title": "y",
            "priority": LOW,
            "status": TODO,
            "assignee_id": ghost,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r_post.status_code == 400


def test_assignee_can_be_pm_or_developer_no_extra_role_rule(pm_env, db_session):
    """No unapproved restriction on WHICH user may be assigned."""
    client, csrf, pm_uid = pm_env
    task = _pm_creates_task(client, csrf, assignee_id=pm_uid)  # PM assigns PM
    assert task["assignee_id"] == pm_uid


# --- DELETE ---------------------------------------------------------------------


def test_pm_delete_204_then_404(pm_env):
    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    resp = client.delete(
        f"/api/tasks/{task['id']}", headers={"X-CSRF-Token": csrf}
    )
    assert resp.status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404


def test_delete_removes_dependent_comments_without_error(pm_env, db_session):
    """Approved cascade behavior applies (comment API arrives later; the
    relationship cascade is already approved at model level)."""
    from app.models import Comment

    client, csrf, _ = pm_env
    task = _pm_creates_task(client, csrf)
    pm_uid = client.get("/api/auth/me").json()["user_id"]
    db_session.add(
        Comment(task_id=task["id"], user_id=pm_uid, content="c")
    )
    db_session.commit()

    resp = client.delete(
        f"/api/tasks/{task['id']}", headers={"X-CSRF-Token": csrf}
    )
    assert resp.status_code == 204


def test_developer_delete_403(pm_env, dev_env):
    pm_client, pm_csrf, _ = pm_env
    dev_client, dev_csrf, _ = dev_env
    task = _pm_creates_task(pm_client, pm_csrf)

    resp = dev_client.delete(
        f"/api/tasks/{task['id']}", headers={"X-CSRF-Token": dev_csrf}
    )
    assert resp.status_code == 403
    assert pm_client.get(f"/api/tasks/{task['id']}").status_code == 200


def test_unauthenticated_delete_401(api_client):
    assert api_client.delete("/api/tasks/1").status_code == 401


def test_delete_missing_task_404(pm_env):
    client, csrf, _ = pm_env
    resp = client.delete("/api/tasks/99999", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 404


def test_delete_requires_csrf(pm_env):
    client, _, _ = pm_env
    task = _pm_creates_task(client, pm_env[1])
    assert (
        client.delete(f"/api/tasks/{task['id']}").status_code == 403
    )


def test_delete_does_not_leak_internal_reason(pm_env, dev_env):
    pm_client, pm_csrf, _ = pm_env
    dev_client, dev_csrf, _ = dev_env
    task = _pm_creates_task(pm_client, pm_csrf)
    resp = dev_client.delete(
        f"/api/tasks/{task['id']}", headers={"X-CSRF-Token": dev_csrf}
    )
    low = resp.text.lower()
    assert resp.status_code == 403
    assert "pm_required" not in low and "delete" not in low
