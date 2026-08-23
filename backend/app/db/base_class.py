"""Model registry imported by Alembic ``env.py``.

Every concrete model must be imported here so Alembic autogenerate sees
the full metadata.

NOTE: ``AuthSession`` is SECURITY INFRASTRUCTURE (server-session state),
not a Product/domain entity. The approved domain set remains exactly
User + Task + Comment.
"""

from app.auth.session_model import AuthSession  # noqa: F401  (infrastructure)
from app.models.comment import Comment  # noqa: F401
from app.models.task import Task  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = ["AuthSession", "Comment", "Task", "User"]
