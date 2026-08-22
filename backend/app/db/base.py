"""Declarative ORM base.

Phase 1 scaffolding: the shared declarative base that Phase 2 domain
models (users, sessions, tasks, comments) will inherit from.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
