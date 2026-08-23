"""Phase 3A migration integrity tests.

Extends the Phase 2 isolation guarantees:
  - destructive round-trips run ONLY on the disposable migration-test DB
  - the normal development database is never downgraded by pytest
  - explicit Alembic URL override remains authoritative (env.py)
"""

from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config


def _alembic_to(url: str, rev: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    if rev == "base":
        command.downgrade(cfg, rev)
    else:
        command.upgrade(cfg, rev)


def test_phase3a_migration_round_trip_isolated(
    mysql_url: str, migration_test_url: str
) -> None:
    """base -> head(3A) verifies both revisions; head -> base reverses."""
    assert _domain_tables(mysql_url), "dev db expected migrated before test"

    _alembic_to(migration_test_url, "head")
    insp = inspect(create_engine(migration_test_url))
    tables = set(insp.get_table_names())
    # Domain tables (Phase 2) + infrastructure table (Phase 3A).
    assert {"users", "tasks", "comments", "auth_sessions"} <= tables

    fks = {
        fk["name"]: (fk["referred_table"], tuple(fk["constrained_columns"]))
        for fk in insp.get_foreign_keys("auth_sessions")
    }
    assert fks["fk_auth_sessions_user_id_users"] == ("users", ("user_id",))

    engine = create_engine(migration_test_url)
    cols = {c["name"] for c in insp.get_columns("auth_sessions")}
    assert cols == {
        "id",
        "token_digest",
        "user_id",
        "csrf_token_digest",
        "created_at",
        "expires_at",
        "revoked_at",
    }
    engine.dispose()

    _alembic_to(migration_test_url, "base")
    remaining = set(inspect(create_engine(migration_test_url)).get_table_names())
    assert not remaining & {"users", "tasks", "comments", "auth_sessions"}


def test_dev_database_not_downgraded_by_migration_tests(
    mysql_url: str, migration_test_url: str
) -> None:
    """REGRESSION SAFEGUARD: dev DB untouched by destructive tests."""
    assert migration_test_url.rpartition("/")[2] != mysql_url.rpartition("/")[2]
    engine = create_engine(mysql_url)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert {"users", "tasks", "comments"} <= names


def _domain_tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return {"users", "tasks", "comments"} & set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
