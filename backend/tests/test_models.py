"""Model structure tests (no database required).

Lock the ORM shape to the authoritative architecture: required vs
optional fields, relationships, and server-managed columns.
"""

from app.db.base import Base
from app.models import Comment, Task, User


def _table(model):
    return Base.metadata.tables[model.__tablename__]


def test_users_columns() -> None:
    cols = {c.name: c for c in _table(User).columns}
    assert set(cols) == {
        "id",
        "email",
        "password_hash",
        "role",
        "created_at",
        "updated_at",
    }
    assert cols["email"].nullable is False
    assert cols["password_hash"].nullable is False  # REQUIRED per architecture
    assert cols["role"].nullable is False


def test_tasks_required_vs_optional() -> None:
    cols = {c.name: c for c in _table(Task).columns}
    required = {n for n, c in cols.items() if c.nullable is False}
    assert {"title", "priority", "status"} <= required
    optional = {n for n, c in cols.items() if c.nullable is True}
    assert {"description", "assignee_id", "due_date"} <= optional


def test_comment_columns_exactly_approved() -> None:
    """Authoritative shape: id, task_id, user_id, content, created_at."""
    cols = {c.name: c for c in _table(Comment).columns}
    assert set(cols) == {"id", "task_id", "user_id", "content", "created_at"}
    assert cols["task_id"].nullable is False
    assert cols["user_id"].nullable is False
    assert cols["content"].nullable is False


def test_foreign_keys() -> None:
    fks = {}
    for t in Base.metadata.tables.values():
        for fk in t.foreign_keys:
            fks[fk.parent.name] = fk.target_fullname
    assert fks["task_id"] == "tasks.id"
    assert fks["user_id"] == "users.id"
    assert fks["assignee_id"] == "users.id"


def test_relationships_declared() -> None:
    user_rels = {r.key for r in User.__mapper__.relationships}
    task_rels = {r.key for r in Task.__mapper__.relationships}
    comment_rels = {r.key for r in Comment.__mapper__.relationships}
    assert {"tasks", "comments"} <= user_rels
    assert {"assignee", "comments"} <= task_rels
    assert {"task", "author"} <= comment_rels  # ORM alias; column is user_id


def test_no_updated_at_on_comment() -> None:
    """No update concept exists for comments — no updated_at column."""
    assert not hasattr(Comment, "updated_at")
    assert "updated_at" not in {c.name for c in _table(Comment).columns}


def test_no_session_entity_in_domain_metadata() -> None:
    """The session store is Phase 3 infrastructure — it must not exist here."""
    assert "sessions" not in Base.metadata.tables
