"""User directory service (Phase 5B prerequisite).

Read-only access to the existing users table with deterministic ORDER
BY id. Authorization is centralized (Phase 3B policies); no role logic
lives here beyond the delegated policy call.
"""

from sqlalchemy.orm import Session

from app.auth import authorization
from app.models import User


def list_users(db: Session, user: User) -> list[User]:
    """Both approved roles may read the directory; deterministic order."""
    authorization.can_view_task(user)
    return list(db.query(User).order_by(User.id).all())
