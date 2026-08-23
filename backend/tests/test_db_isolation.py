"""Database-isolation regression safeguards (Phase 3A review).

Proves structurally that:
  - pytest binds ONLY to the dedicated integration database (taskdb_test)
  - destructive migration tests bind ONLY to taskdb_migration_test
  - the three databases are mutually distinct
  - the fixture-cleanup helper refuses to purge any non-test database
"""

import pytest
from sqlalchemy import create_engine

from app.core.config import settings
from tests.conftest import DEV_DB_NAME, MIGRATION_TEST_DB, TEST_DB_NAME, _purge


def test_pytest_is_bound_to_dedicated_integration_database() -> None:
    """Isolation comes from conftest constants/URLs, not app settings."""
    assert TEST_DB_NAME == "taskdb_test" != DEV_DB_NAME == "taskdb"
    assert MIGRATION_TEST_DB == "taskdb_migration_test"
    assert len({TEST_DB_NAME, MIGRATION_TEST_DB, DEV_DB_NAME}) == 3


def test_three_databases_are_mutually_distinct(mysql_url, migration_test_url) -> None:
    integration = mysql_url.rpartition("/")[2].split("?")[0]
    migration = migration_test_url.rpartition("/")[2].split("?")[0]
    assert integration == TEST_DB_NAME
    assert migration == MIGRATION_TEST_DB == "taskdb_migration_test"
    assert len({integration, migration, DEV_DB_NAME}) == 3


def test_cleanup_helper_refuses_to_purge_development_database() -> None:
    """The purge routine must hard-fail on anything but taskdb_test."""
    rogue = create_engine(
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{DEV_DB_NAME}?charset=utf8mb4"
    )
    with pytest.raises(RuntimeError, match=DEV_DB_NAME):
        _purge(rogue)


def test_fixtures_operate_on_the_integration_database(db_engine, db_session) -> None:
    assert db_engine.url.database == TEST_DB_NAME
    assert db_session.bind.url.database == TEST_DB_NAME
