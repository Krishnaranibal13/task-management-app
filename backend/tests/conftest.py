"""Pytest configuration with STRICT three-database isolation.

Database roles (local development only):
  - taskdb                : normal local DEVELOPMENT. Pytest must NEVER
                            destructively modify it.
  - taskdb_test           : ordinary pytest integration/API/session tests;
                            disposable data; truncation allowed HERE only.
  - taskdb_migration_test : destructive Alembic round-trip tests ONLY.

SAFETY CONTRACT
---------------
  - DB-backed tests bind exclusively to ``taskdb_test``. There is NO
    fallback to the development database: if it is unavailable, tests
    SKIP with guidance (they never silently run against taskdb).
  - Destructive migration round-trips bind exclusively to
    ``taskdb_migration_test`` and never touch the other databases.
  - The fixture purge helper hard-refuses to purge any database other
    than taskdb_test.
  - Tests exercise REAL MySQL — SQLite results are never used as
    evidence of MySQL behavior.

Provisioning (idempotent, non-destructive, existing Docker volumes are
preserved): run
``infrastructure/mysql/initdb/03-local-test-databases.sql`` once as root,
or let the compose init mount apply it on a fresh volume.
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings

# Canonical, review-mandated database names.
DEV_DB_NAME = "taskdb"
TEST_DB_NAME = "taskdb_test"
MIGRATION_TEST_DB = os.environ.get("MIGRATION_TEST_DB", "taskdb_migration_test")


def _url(database: str) -> str:
    return (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{database}?charset=utf8mb4"
    )


def _purge(db_engine) -> None:
    """Truncate ALL app tables — permitted ONLY on the integration test DB.

    Hard-fails on any other database so cleanup can never hit the
    development database by accident.
    """
    dbname = db_engine.url.database
    if dbname != TEST_DB_NAME:
        raise RuntimeError(
            f"Refusing to purge '{dbname}': fixture cleanup is restricted "
            f"to '{TEST_DB_NAME}' (development database '{DEV_DB_NAME}' "
            "must never be truncated by pytest)."
        )
    with db_engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in ("auth_sessions", "comments", "tasks", "users"):
            conn.execute(text(f"TRUNCATE TABLE {table}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


def _ensure_schema(engine, url: str) -> None:
    """Apply Alembic migrations (UPGRADE ONLY) if the schema is absent."""
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


def _provision_database(database: str) -> bool:
    """Create a test database + scoped grants if absent (LOCAL/TEST only).

    Returns True when provisioning is possible; False when the connected
    account lacks privileges (callers then skip with guidance rather than
    fall back to another database).
    """
    server_url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/?charset=utf8mb4"
    )
    admin = create_engine(server_url)
    try:
        with admin.begin() as conn:
            exists = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.SCHEMATA "
                    "WHERE schema_name = :db"
                ),
                {"db": database},
            ).scalar()
            if int(exists):
                return True  # already provisioned (e.g. by initdb script)
            conn.execute(
                text(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4")
            )
            # Scoped grant for THIS test database only.
            conn.execute(
                text(f"GRANT ALL PRIVILEGES ON `{database}`.* TO '{settings.MYSQL_USER}'@'%'")
            )
            conn.execute(text("FLUSH PRIVILEGES"))
        return True
    except Exception:
        return False
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def dev_mysql_url() -> str:
    """URL of the normal development database — NEVER purged by tests."""
    return _url(DEV_DB_NAME)


@pytest.fixture(scope="session")
def mysql_url() -> str:
    """URL of the dedicated INTEGRATION TEST database (taskdb_test).

    Provisioned idempotently when possible; otherwise tests skip with
    explicit guidance. There is deliberately NO fallback to taskdb.
    """
    engine = create_engine(_url(TEST_DB_NAME), pool_pre_ping=True)
    try:
        with engine.connect():
            pass
    except Exception:
        if not _provision_database(TEST_DB_NAME):
            pytest.skip(
                f"Test database '{TEST_DB_NAME}' unavailable and could not be "
                f"created. Run infrastructure/mysql/initdb/"
                f"03-local-test-databases.sql as an admin (e.g. docker exec "
                f"taskmgmt-db sh -c 'MYSQL_PWD=... mysql -uroot < /docker-entrypoint-"
                f"initdb.d/03-local-test-databases.sql') and re-run pytest. "
                f"Tests never fall back to the development database."
            )
        # Retry once after successful provisioning.
        try:
            with engine.connect():
                pass
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Test database '{TEST_DB_NAME}' still unreachable: {exc}")
    _ensure_schema(engine, _url(TEST_DB_NAME))
    yield _url(TEST_DB_NAME)
    engine.dispose()


@pytest.fixture(scope="session")
def db_engine(mysql_url: str):
    """Session-scoped engine bound EXCLUSIVELY to the integration test DB."""
    engine = create_engine(mysql_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def migration_test_url():
    """Dedicated DISPOSABLE database for DESTRUCTIVE migration tests."""
    assert MIGRATION_TEST_DB != DEV_DB_NAME, "safety misconfiguration"
    if not _provision_database(MIGRATION_TEST_DB):
        pytest.skip(
            f"Migration-test database '{MIGRATION_TEST_DB}' unavailable and "
            "could not be created; destructive migration round-trips must "
            "never target any other database. Apply "
            "infrastructure/mysql/initdb/03-local-test-databases.sql first."
        )
    yield _url(MIGRATION_TEST_DB)


@pytest.fixture()
def db_session(db_engine):
    """Fresh ORM session on taskdb_test; tables purged before AND after.

    Cleanup is structurally restricted to the integration test database
    (see :func:`_purge`).
    """
    _purge(db_engine)
    session = Session(bind=db_engine, expire_on_commit=False)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        _purge(db_engine)


# Safe test-only dummy value standing in for a Phase 3 Argon2id hash.
DUMMY_PASSWORD_HASH = "test-only-dummy-hash-not-a-real-credential"


@pytest.fixture()
def make_user(db_session):
    """Factory: create a User row (password_hash required by the model).

    Commits so rows are visible to API-layer connections (the FastAPI
    app uses its own session/transaction).
    """

    def _create(email: str, role: str, password_hash: str = DUMMY_PASSWORD_HASH):
        from app.models import User

        user = User(email=email, role=role, password_hash=password_hash)
        db_session.add(user)
        db_session.flush()
        db_session.commit()
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


# --- Phase 3A: authentication/session fixtures --------------------------


@pytest.fixture()
def make_api_client(mysql_url):
    """Factory producing app clients bound to the INTEGRATION TEST database."""
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.core.config import settings
    from app.db.session import get_db
    from app.main import create_app

    def _make(raise_server_exceptions: bool = True):
        saved_lifetime = settings.SESSION_LIFETIME_SECONDS
        settings.SESSION_LIFETIME_SECONDS = 3600  # test-only value

        test_engine = create_engine(mysql_url, pool_pre_ping=True)
        TestSession = sessionmaker(bind=test_engine, expire_on_commit=False)

        def _override_get_db():
            s = TestSession()
            try:
                yield s
            finally:
                s.close()

        app = create_app()
        app.dependency_overrides[get_db] = _override_get_db
        return (
            app,
            TestClient(app, raise_server_exceptions=raise_server_exceptions),
            test_engine,
        )

    return _make


@pytest.fixture()
def api_client(make_api_client):
    """Fresh app client per test, bound to taskdb_test via get_db override.

    The application-under-test reads/writes the integration test
    database — never the development database. A TEST-ONLY session
    lifetime is injected; production values remain deployment decisions.
    """
    app, client, test_engine = make_api_client()
    try:
        yield client
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()


@pytest.fixture()
def authed_client(api_client, make_user):
    """Login helper: returns (client, csrf_token).

    Creates its user via the real Argon2id hasher, then performs a real
    login against /api/auth/login.
    """
    from app.auth.security import hash_password

    def _login(
        email: str = "auth@example.com",
        password: str = "correct horse battery staple",
        role: str = "pm",
    ):
        make_user(email, role, password_hash=hash_password(password))
        resp = api_client.post(
            "/api/auth/login", json={"email": email, "password": password}
        )
        assert resp.status_code == 200, resp.text
        return api_client, resp.json()["csrf_token"]

    return _login


@pytest.fixture()
def inject_session_settings():
    """Temporarily override session/rate-limit configuration for a test."""
    from app.core.config import settings

    def _apply(**overrides):
        saved = {
            k: getattr(settings, k)
            for k in (
                "SESSION_LIFETIME_SECONDS",
                "SESSION_COOKIE_NAME",
                "LOGIN_RATE_LIMIT_MAX_ATTEMPTS",
                "LOGIN_RATE_LIMIT_WINDOW_SECONDS",
                "ENVIRONMENT",
            )
        }
        for key, value in overrides.items():
            setattr(settings, key, value)
        return lambda: [setattr(settings, k, v) for k, v in saved.items()]

    yield _apply


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Ensure test-injected throttle state never leaks between tests."""
    yield
    from app.auth import rate_limit

    rate_limit.configure_for_tests(None, None)
