"""Database engine and session factory for MySQL.

Phase 1: connection scaffolding only. No models are mapped yet; the ORM
base arrives with Phase 2 (database/domain).
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def build_database_url() -> str:
    """Compose the MySQL connection URL from environment settings.

    Credentials are injected via URL parameters and are never logged.
    """
    return (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}"
        "?charset=utf8mb4"
    )


engine: Engine = create_engine(
    build_database_url(),
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
