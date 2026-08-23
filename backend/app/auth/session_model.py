"""Infrastructure session persistence (NOT a Product/domain entity).

The approved Product domain is exactly User + Task + Comment. This table
stores SECURITY STATE backing stateful server sessions:

  - lookup by session-token DIGEST (the raw credential is never stored)
  - association to exactly one User
  - creation time
  - expiration
  - revocation (logout invalidation)

Kept deliberately separate from ``app.models`` (domain).
"""

import datetime
import enum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuthSession(Base):
    """One server-side session (infrastructure/security state)."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        # The raw token is never stored; lookups go through the digest.
        Index("uq_auth_sessions_token_digest", "token_digest", unique=True),
        Index("ix_auth_sessions_user_id", "user_id"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # SHA-256 digest of the opaque session credential (hex, 64 chars).
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_auth_sessions_user_id_users", ondelete="CASCADE"),
        nullable=False,
    )

    # Session-bound CSRF synchronizer token: stored as a digest as well;
    # the raw token lives only with the client.
    csrf_token_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(), nullable=False
    )
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(), nullable=True
    )

    user = relationship("User", viewonly=True)

    @property
    def is_active(self) -> bool:
        """Active = not revoked and not expired (UTC-naive comparison)."""
        if self.revoked_at is not None:
            return False
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        return now < self.expires_at
