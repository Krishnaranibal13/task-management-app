"""Database integration tests — run against REAL Docker MySQL.

These tests skip if MySQL is unreachable; SQLite is never used as
substitute evidence.
"""

import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, StatementError

from app.models import Comment, Task, User
from tests.conftest import DUMMY_PASSWORD_HASH


def test_create_and_read_user(db_session, make_user) -> None:
    u = make_user("pm@example.com", "pm")
    db_session.expire_all()
    loaded = db_session.get(User, u.id)
    assert loaded.email == "pm@example.com"
    assert loaded.role.value == "pm"


def test_user_requires_password_hash(db_session) -> None:
    db_session.add(User(email="nohash@example.com", role="developer"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_duplicate_email_rejected(db_session, make_user) -> None:
    make_user("dup@example.com", "developer")
    db_session.add(User(email="dup@example.com", role="pm", password_hash=DUMMY_PASSWORD_HASH))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_invalid_role_rejected_at_db_level(db_session) -> None:
    db_session.add(User(email="x@example.com", role="admin", password_hash=DUMMY_PASSWORD_HASH))
    with pytest.raises((IntegrityError, StatementError)):
        db_session.commit()


def test_raw_insert_with_unapproved_role_violates_check(
    db_engine, mysql_url
) -> None:
    """Bypassing the ORM still hits the CHECK constraint.

    PyMySQL maps CHECK-violation errno 3819 to OperationalError; FK/unique
    violations surface as IntegrityError. Both are hard failures.
    """
    import sqlalchemy as sa

    engine = sa.create_engine(mysql_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (email, password_hash, role) "
                "VALUES ('raw@example.com', 'dummy', 'developer')"
            )
        )
        with pytest.raises((sa.exc.IntegrityError, sa.exc.OperationalError)):
            conn.execute(
                text(
                    "INSERT INTO users (email, password_hash, role) "
                    "VALUES ('raw2@example.com', 'dummy', 'superuser')"
                )
            )
    engine.dispose()


def test_task_requires_title(db_session) -> None:
    db_session.add(Task(priority="low", status="to_do"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_task_requires_priority_and_status(db_session) -> None:
    db_session.add(Task(title="no enums"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_invalid_status_rejected_at_db_level(db_session) -> None:
    db_session.add(Task(title="t", priority="low", status="archived"))
    with pytest.raises((IntegrityError, StatementError)):
        db_session.commit()


def test_invalid_priority_rejected_at_db_level(db_session) -> None:
    db_session.add(Task(title="t", priority="urgent", status="to_do"))
    with pytest.raises((IntegrityError, StatementError)):
        db_session.commit()


def test_optional_fields_allow_null(db_session, make_task) -> None:
    t = make_task()
    assert t.description is None
    assert t.assignee_id is None  # zero-or-one assignee: NULL supported
    assert t.due_date is None


def test_due_date_roundtrip(db_session, make_task) -> None:
    t = make_task(due_date=datetime.date(2026, 12, 24))
    db_session.expire_all()
    assert db_session.get(Task, t.id).due_date == datetime.date(2026, 12, 24)


def test_relationships(db_session, make_user, make_task) -> None:
    pm = make_user("rel-pm@example.com", "pm")
    dev = make_user("rel-dev@example.com", "developer")
    t1 = make_task(title="one", assignee_id=dev.id)
    t2 = make_task(title="two", assignee_id=dev.id)
    c = Comment(task_id=t1.id, user_id=pm.id, content="first!")
    db_session.add(c)
    db_session.flush()

    db_session.refresh(dev)
    db_session.refresh(t1)
    assert {x.title for x in dev.tasks} == {"one", "two"}
    assert t1.assignee.email == "rel-dev@example.com"
    assert t1.comments[0].content == "first!"
    assert pm.comments[0].task_id == t1.id


def test_comment_created_at_server_default(db_session, make_user, make_task) -> None:
    u = make_user("ts@example.com", "developer")
    t = make_task()
    c = Comment(task_id=t.id, user_id=u.id, content="when?")
    db_session.add(c)
    db_session.flush()
    db_session.expire_all()
    loaded = db_session.get(Comment, c.id)
    assert loaded.created_at is not None
