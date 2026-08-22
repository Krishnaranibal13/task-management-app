"""Alembic migration integrity tests.

DESTRUCTIVE round-trips run EXCLUSIVELY against the dedicated disposable
migration-test database (``taskdb_migration_test``) — never against the
ordinary development database. A regression safeguard asserts the
development database is untouched by these tests.
"""

from sqlalchemy import create_engine, inspect, text

from alembic import command
from alembic.config import Config


def _alembic_to(url: str, rev: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    if rev == "base":
        command.downgrade(cfg, rev)
    else:
        command.upgrade(cfg, rev)


def _domain_tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return {"users", "tasks", "comments"} & set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_destructive_round_trip_isolated(
    mysql_url: str, migration_test_url: str
) -> None:
    """head -> base -> head on the DISPOSABLE database only."""
    # Safeguard: remember the dev database's domain tables before.
    assert _domain_tables(mysql_url), "dev db expected migrated before test"

    _alembic_to(migration_test_url, "base")

    engine = create_engine(migration_test_url)
    remaining = set(inspect(engine).get_table_names())
    assert not remaining & {"users", "tasks", "comments"}, (
        f"downgrade left tables behind: {remaining}"
    )
    engine.dispose()

    _alembic_to(migration_test_url, "head")

    insp = inspect(create_engine(migration_test_url))
    tables = set(insp.get_table_names())
    assert {"users", "tasks", "comments"} <= tables

    fks = {
        fk["name"]: (fk["referred_table"], tuple(fk["constrained_columns"]))
        for t in ("tasks", "comments")
        for fk in insp.get_foreign_keys(t)
    }
    assert fks["fk_tasks_assignee_id_users"] == ("users", ("assignee_id",))
    assert fks["fk_comments_task_id_tasks"] == ("tasks", ("task_id",))
    assert fks["fk_comments_user_id_users"] == ("users", ("user_id",))

    checks = {
        c["name"]
        for t in ("tasks", "users")
        for c in insp.get_check_constraints(t)
    }
    assert "ck_tasks_status_values" in checks
    assert "ck_tasks_priority_values" in checks
    assert "ck_users_role_values" in checks


def test_dev_database_not_downgraded_by_migration_tests(
    mysql_url: str, migration_test_url: str
) -> None:
    """REGRESSION SAFEGUARD: destructive tests never touch the dev DB."""
    assert migration_test_url.rpartition("/")[2] != mysql_url.rpartition("/")[2]
    assert _domain_tables(mysql_url) == {"users", "tasks", "comments"}
