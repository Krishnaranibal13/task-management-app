"""User domain model — authoritative architecture shape.

Fields: id, email (unique, required), password_hash (REQUIRED),
role ("pm" | "developer"), created_at, updated_at.

Phase 2 scope is persistence structure only; hashing/verification
behavior arrives in Phase 3.
"""

from sqlalchemy import CheckConstraint, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import UserRole
from app.models.mixins import TimestampMixin


class User(TimestampMixin, Base):
    """An application user: Project Manager or Developer."""

    __tablename__ = "users"
    __table_args__ = (
        # Database-layer enforcement of the approved role set.
        CheckConstraint(
            "role IN ('pm', 'developer')",
            name="role_values",
        ),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    # Required storage column. Hashing/verification behavior is Phase 3;
    # no hashing logic exists in this phase.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        # Persist the approved VALUES ("pm"/"developer").
        Enum(
            UserRole,
            native_enum=False,
            length=32,
            validate_strings=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )

    tasks = relationship(
        "Task",
        back_populates="assignee",
        foreign_keys="Task.assignee_id",
    )
    comments = relationship(
        "Comment",
        back_populates="author",
        foreign_keys="Comment.user_id",
    )
