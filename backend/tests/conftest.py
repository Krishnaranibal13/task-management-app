"""Pytest configuration.

Unit tests run anywhere; database-integration tests require the Docker
MySQL (`docker compose up -d db`) and skip automatically when it is
unreachable. Tests exercise REAL MySQL — SQLite results are never used
as evidence of MySQL behavior.

SAFETY CONTRACT
---------------
Ordinary tests may only ever *upgrade* the configured development
database (`settings.MYSQL_DB`, e.g. ``taskdb``) if anything. Destructive
migration round-trips (base <-> head) run EXCLUSIVELY against a
dedicated disposable database (see ``migration_test_url``) and can never
target the development database.
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings


def _url(database: str | None = None) -> str:
    db_part = f"/{database}" if database else ""
    return (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}{db_part}?charset=utf8mb4"
    )


# Disposable-database administration (LOCAL TESTING ONLY).
# Defaults match the local compose placeholders published in
# .env.example; they are not real secrets. Override via environment when
# needed. Refused outside the local environment.
_MIGRATION_TEST_DB = os.environ.get("MIGRATION_TEST_DB", "taskdb_migration_test")


def _admin_url_for(mysql_url: str) -> str:
    """Server URL with no default database selected."""
    return mysql_url.rpartition("/")[0]


@pytest.fixture(scope="session")
def mysql_url() -> str:
    """URL of the ordinary development database."""
    return _url(settings.MYSQL_DB)


@pytest.fixture(scope="session")
def db_engine(mysql_url: str):
    try:
        engine = create_engine(mysql_url, pool_pre_ping=True)
        with engine.connect():
            pass
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"MySQL not reachable ({exc}); start docker compose db")
    _ensure_schema(engine, mysql_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def migration_test_url(mysql_url: str):
    """Dedicated DISPOSABLE database for destructive migration tests.

    Created and dropped around the session; never the development DB.
    Skips with guidance when the connected account cannot create
    databases (production-like setups) — destructive tests must never
    fall back to the development database.
    """
    dev_db = mysql_url.rpartition("/")[2]
    assert _MIGRATION_TEST_DB != dev_db, "safety misconfiguration"

    admin = create_engine(_admin_url_for(mysql_url))
    try:
        with admin.begin() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{_MIGRATION_TEST_DB}` "
                    "CHARACTER SET utf8mb4"
                )
            )
    except Exception as exc:
        admin.dispose()
        pytest.skip(
            "cannot create disposable migration-test database "
            f"( {_MIGRATION_TEST_DB} ): {exc}. Destructive migration "
            "round-trips must run in an isolated environment."
        )

    try:
        yield f"{mysql_url.rpartition('/')[0]}/{_MIGRATION_TEST_DB}"
    finally:
        with admin.begin() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS `{_MIGRATION_TEST_DB}`"))
        admin.dispose()


def _ensure_schema(engine, url: str) -> None:
    """Apply Alembic migrations if the domain schema is absent (upgrade only)."""
    from alembic import command
    from alembic.config import Config

    with engine.connect() as conn:
        present = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'users'"
            )
        ).scalar()
    if not int(present):
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")


@pytest.fixture()
def db_session(db_engine):
    """Fresh ORM session; written rows are truncated after each test."""
    session = Session(bind=db_engine, expire_on_commit=False)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        with db_engine.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            conn.execute(text("TRUNCATE TABLE comments"))
            conn.execute(text("TRUNCATE TABLE tasks"))
            conn.execute(text("TRUNCATE TABLE users"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


# Safe test-only dummy value standing in for a Phase 3 Argon2id hash.
DUMMY_PASSWORD_HASH = "test-only-dummy-hash-not-a-real-credential"


@pytest.fixture()
def make_user(db_session):
    """Factory: create a User row (password_hash required by the model)."""

    def _create(email: str, role: str, password_hash: str = DUMMY_PASSWORD_HASH):
        from app.models import User

        user = User(email=email, role=role, password_hash=password_hash)
        db_session.add(user)
        db_session.flush()
        return user

    return _create


@pytest.fixture()
def make_task(db_session):
    """Factory: create a Task row."""

    def _create(**overrides):
        from app.models import Task, TaskPriority, TaskStatus

        params = {
            "title": "Sample task",
            "priority": TaskPriority.MEDIUM,
            "status": TaskStatus.TO_DO,
        }
        params.update(overrides)
        task = Task(**params)
        db_session.add(task)
        db_session.flush()
        return task

    return _create
