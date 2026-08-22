"""Alembic environment for the Task Management MVP backend."""

from logging.config import fileConfig

from alembic import context

# Import the ORM base so metadata is populated for autogenerate.
from app.db.base import Base
from app.db.base_class import User, Task, Comment  # noqa: F401
from app.db.session import build_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Phase 1: metadata contains no concrete models yet (they arrive in
# Phase 2+). Alembic is fully wired; the first revision will be created
# when domain models land.
target_metadata = Base.metadata


def _database_url() -> str:
    """Resolve the database URL (never logged).

    An explicitly configured ``sqlalchemy.url`` (e.g. set by tests/CI to
    point at a disposable database) takes precedence. Otherwise the URL
    comes from application environment settings. This precedence is a
    SAFETY feature: destructive migration tests must be able to target
    their disposable database deterministically.
    """
    override = config.get_main_option("sqlalchemy.url")
    if override:
        return override
    return build_database_url()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live database connection."""
    from sqlalchemy import engine_from_config, pool

    # Build the engine config programmatically so credentials stay out of
    # the INI file on disk.
    configuration = {
        "sqlalchemy.url": _database_url(),
    }
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
