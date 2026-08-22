"""Model registry imported by Alembic ``env.py``.

Every concrete model must be imported here so Alembic autogenerate sees
the full metadata.
"""

from app.models.comment import Comment  # noqa: F401
from app.models.task import Task  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = ["Comment", "Task", "User"]
