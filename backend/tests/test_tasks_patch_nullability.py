"""Phase 4A final correction: PATCH nullability contract.

Required fields (title, priority, status):
  - MAY be omitted in a partial PATCH
  - MUST NOT be explicitly null → ordinary validation failure (422),
    never HTTP 500 and never a database-level rejection.

Nullable fields (description, assignee_id, due_date):
  - explicit null remains valid (assignee_id null = PM unassign).

Partial semantics:
  - omitted fields keep their previous values (exclude_unset).
"""

import pytest
from sqlalchemy import text

from app.auth.security import hash_password
from app.models import TaskPriority, TaskStatus

TODO = TaskStatus.TO_DO.value
IN_PROGRESS = TaskStatus.IN_PROGRESS.value
HIGH = TaskPriority.HIGH.value


@pytest.fixture()
def pm_env(make_api_client, make_user):
    """Logged-in PM with its OWN client+cookie jar."""
    email = "pm-null@example.com"
    make_user(email, "pm", password_hash=hash_password("pw123456"))
    app, client, engine = make_api_client()
    resp = client.post(
        "/api/auth/login", json={"email": email, "password": "pw123456"}
    )
    assert resp.status_code == 200, resp.text
    uid = client.get("/api/auth/me").json()["user_id"]
    return client, resp.json()["csrf_token"], uid


def _create_full_task(client, csrf, db_session):
    """Task with EVERY field populated (required + optional).

    Ensures its developer assignee exists in taskdb_test.
    """
    from app.models import User

    dev_id = db_session.execute(
        text("SELECT id FROM users WHERE email='dev-null@example.com'")
    ).scalar()
    if dev_id is None:
        db_session.add(
            User(email="dev-null@example.com", role="developer",
                 password_hash="test-only-not-a-real-hash")
        )
        db_session.commit()
        dev_id = int(
            db_session.execute(
                text("SELECT id FROM users WHERE email='dev-null@example.com'")
            ).scalar_one()
        )

    payload = {
        "title": "Original A",
        "description": "original description",
        "assignee_id": int(dev_id),
        "priority": HIGH,
        "status": IN_PROGRESS,
        "due_date": "2026-09-30",
    }
    resp = client.post(
        "/api/tasks", json=payload, headers={"X-CSRF-Token": csrf}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- required-field explicit nulls are VALIDATION rejections --------------


def test_patch_title_null_rejected_as_validation(pm_env):
    client, csrf, _ = pm_env
    task_resp = client.post(
        "/api/tasks",
        json={"title": "t", "priority": HIGH, "status": TODO},
        headers={"X-CSRF-Token": csrf},
    )
    assert task_resp.status_code == 201
    tid = task_resp.json()["id"]

    resp = client.patch(
        f"/api/tasks/{tid}",
        json={"title": None},
        headers={"X-CSRF-Token": csrf},
    )
    # Ordinary validation error — sanitized 422, NOT 500/400/db error.
    assert resp.status_code == 422, resp.text
    assert "must not be null" not in resp.text  # internal message hidden
    # Persisted task unchanged.
    assert client.get(f"/api/tasks/{tid}").json()["title"] == "t"


def test_patch_priority_null_rejected_as_validation(pm_env):
    client, csrf, _ = pm_env
    task_resp = client.post(
        "/api/tasks",
        json={"title": "t", "priority": HIGH, "status": TODO},
        headers={"X-CSRF-Token": csrf},
    )
    tid = task_resp.json()["id"]

    resp = client.patch(
        f"/api/tasks/{tid}",
        json={"priority": None},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422, resp.text
    assert client.get(f"/api/tasks/{tid}").json()["priority"] == HIGH


def test_patch_status_null_rejected_as_validation(pm_env):
    client, csrf, _ = pm_env
    task_resp = client.post(
        "/api/tasks",
        json={"title": "t", "priority": HIGH, "status": TODO},
        headers={"X-CSRF-Token": csrf},
    )
    tid = task_resp.json()["id"]

    resp = client.patch(
        f"/api/tasks/{tid}",
        json={"status": None},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422, resp.text
    assert client.get(f"/api/tasks/{tid}").json()["status"] == TODO


# --- nullable fields still accept explicit null ----------------------------


def test_nullable_fields_explicit_null_still_allowed(pm_env, db_session):
    client, csrf, _ = pm_env
    task = _create_full_task(client, csrf, db_session)
    resp = client.patch(
        f"/api/tasks/{task['id']}",
        json={"description": None, "due_date": None},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["description"] is None
    assert body["due_date"] is None
    # Required + other fields untouched.
    assert body["title"] == "Original A"
    assert body["priority"] == HIGH


def test_assignee_null_remains_pm_unassign(pm_env, db_session):
    client, csrf, _ = pm_env
    task = _create_full_task(client, csrf, db_session)
    assert task["assignee_id"] is not None

    resp = client.patch(
        f"/api/tasks/{task['id']}",
        json={"assignee_id": None},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["assignee_id"] is None


# --- true partial semantics: omission preserves values --------------------


def test_partial_patch_changes_only_supplied_field(pm_env, db_session):
    client, csrf, _ = pm_env
    task = _create_full_task(client, csrf, db_session)
    before = client.get(f"/api/tasks/{task['id']}").json()

    resp = client.patch(
        f"/api/tasks/{task['id']}",
        json={"title": "Updated B"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    after = resp.json()

    assert after["title"] == "Updated B"
    for field in ("description", "priority", "status", "assignee_id", "due_date"):
        assert after[field] == before[field], f"omitted {field} changed"


def test_empty_patch_object_leaves_task_unchanged(pm_env):
    """PATCH {} is permitted (no approved minimum-one rule) and is a no-op."""
    client, csrf, _ = pm_env
    task_resp = client.post(
        "/api/tasks",
        json={"title": "noop", "priority": HIGH, "status": TODO},
        headers={"X-CSRF-Token": csrf},
    )
    tid = task_resp.json()["id"]
    before = client.get(f"/api/tasks/{tid}").json()

    resp = client.patch(
        f"/api/tasks/{tid}", json={}, headers={"X-CSRF-Token": csrf}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == before


# --- dedicated status endpoint: exactly one non-null status ---------------


def test_status_endpoint_null_status_rejected(pm_env):
    client, csrf, _ = pm_env
    task_resp = client.post(
        "/api/tasks",
        json={"title": "s", "priority": HIGH, "status": TODO},
        headers={"X-CSRF-Token": csrf},
    )
    tid = task_resp.json()["id"]
    resp = client.patch(
        f"/api/tasks/{tid}/status",
        json={"status": None},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422, resp.text
    assert client.get(f"/api/tasks/{tid}").json()["status"] == TODO
