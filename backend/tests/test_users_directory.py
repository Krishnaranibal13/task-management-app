"""Phase 5B prerequisite: user directory endpoint tests.

Contract under test (GET /api/users):
  - response.json() is DIRECTLY a JSON array (no wrapper object)
  - 401 unauthenticated; 200 for both approved roles
  - every entry has exactly {id, email, role}
  - password_hash / timestamps / session data absent
  - deterministic ORDER BY id
  - GET-only: no user mutation routes exist anywhere in the app
  - unknown role fails closed at the schema layer (ValidationError)
"""

import pytest
from pydantic import ValidationError

from app.auth.security import hash_password
from app.models.enums import UserRole
from app.schemas.user import UserDirectoryEntry


@pytest.fixture()
def seeded_users(make_user):
    """Two users inserted in non-id order to prove deterministic sort."""
    make_user("dir-dev@example.com", "developer",
              password_hash=hash_password("pw123456"))
    make_user("dir-pm@example.com", "pm",
              password_hash=hash_password("pw123456"))


def _login_and_fetch(api_client, email: str):
    api_client.post(
        "/api/auth/login", json={"email": email, "password": "pw123456"}
    )
    resp = api_client.get("/api/users")
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- A/B/C: authentication + role access -----------------------------------


def test_unauthenticated_users_401(api_client):
    assert api_client.get("/api/users").status_code == 401


def test_pm_can_read_directory(api_client, make_user, seeded_users):
    make_user("dir-caller-pm@example.com", "pm",
              password_hash=hash_password("pw123456"))
    assert _login_and_fetch(api_client, "dir-caller-pm@example.com") is not None


def test_developer_can_read_directory(api_client, make_user, seeded_users):
    make_user("dir-caller-dev@example.com", "developer",
              password_hash=hash_password("pw123456"))
    assert _login_and_fetch(api_client, "dir-caller-dev@example.com") is not None


# --- D/E/F/G/H/I/L: response contract ---------------------------------------


@pytest.fixture()
def directory(api_client, make_user, seeded_users):
    make_user("dir-viewer@example.com", "pm",
              password_hash=hash_password("pw123456"))
    return _login_and_fetch(api_client, "dir-viewer@example.com")


def test_response_is_directly_a_json_array(directory):
    """The API must NOT wrap the list (e.g. {"users": [...]})."""
    assert isinstance(directory, list)
    assert len(directory) >= 3


def test_entries_contain_exactly_approved_fields(directory):
    for entry in directory:
        assert set(entry.keys()) == {"id", "email", "role"}


def test_password_hash_absent_everywhere(directory):
    text = str(directory).lower()
    assert "password" not in text and "hash" not in text


def test_timestamps_absent_everywhere(directory):
    text = str(directory).lower()
    assert "created_at" not in text and "updated_at" not in text


def test_session_security_fields_absent_everywhere(directory):
    text = str(directory).lower()
    for banned in (
        "session", "token", "csrf", "cookie", "digest", "revoked", "expires",
    ):
        assert banned not in text, f"leaked: {banned}"


def test_both_roles_serialize_correctly(directory):
    roles = {e["role"] for e in directory}
    assert {"pm", "developer"} <= roles
    for e in directory:
        assert e["role"] in ("pm", "developer")


def test_deterministic_ordering_by_id(directory):
    ids = [e["id"] for e in directory]
    assert ids == sorted(ids)


# --- J/K: CSRF not required; no mutation routes -------------------------------


def test_get_requires_no_csrf_header(api_client, make_user, seeded_users):
    make_user("dir-nocsrf@example.com", "pm",
              password_hash=hash_password("pw123456"))
    api_client.post(
        "/api/auth/login",
        json={"email": "dir-nocsrf@example.com", "password": "pw123456"},
    )
    # No X-CSRF-Token header at all.
    assert api_client.get("/api/users").status_code == 200


def test_no_user_mutation_routes_exist():
    from app.main import create_app

    methods_by_path = {}
    for r in create_app().routes:
        p = getattr(r, "path", "")
        if p.startswith("/api/users"):
            methods_by_path.setdefault(p, set()).update(
                m.upper() for m in getattr(r, "methods", set())
            )
    assert methods_by_path == {"/api/users": {"GET"}}


# --- unknown role fails closed at the SCHEMA layer (precise) ------------------


def test_unknown_role_rejected_by_response_schema():
    """'superadmin' must raise Pydantic ValidationError — never serialize
    as a valid Product role."""
    with pytest.raises(ValidationError):
        UserDirectoryEntry(id=1, email="x@example.com", role="superadmin")


def test_approved_roles_accepted_by_response_schema():
    for role in (UserRole.PROJECT_MANAGER, UserRole.DEVELOPER,
                 UserRole.PROJECT_MANAGER.value, UserRole.DEVELOPER.value):
        entry = UserDirectoryEntry(id=1, email="x@example.com", role=role)
        assert entry.role in (UserRole.PROJECT_MANAGER, UserRole.DEVELOPER)


def test_extra_fields_rejected_by_entry_schema():
    with pytest.raises(ValidationError):
        UserDirectoryEntry(
            id=1, email="x@example.com", role="pm",
            password_hash="should-never-be-allowed",
        )


def test_database_check_constraint_rejects_unknown_role(db_engine):
    """Additional defense-in-depth: the DB CHECK constraint rejects an
    unapproved role with the PRECISE database exception (errno 3819 →
    OperationalError via PyMySQL) if raw SQL ever bypassed the ORM."""
    import sqlalchemy.exc

    from sqlalchemy import text

    with db_engine.begin() as conn:
        try:
            conn.execute(
                text(
                    "INSERT INTO users (email, role, password_hash) "
                    "VALUES ('ghost-role@example.com', 'superadmin', 'x')"
                )
            )
        except sqlalchemy.exc.OperationalError as exc:
            assert "3819" in str(exc) or "ck_users_role_values" in str(exc)
        else:
            # If the insert unexpectedly succeeded, clean up and fail.
            conn.execute(text(
                "DELETE FROM users WHERE email = 'ghost-role@example.com'"
            ))
            raise AssertionError("DB CHECK constraint did not reject 'superadmin'")
