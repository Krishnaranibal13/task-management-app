"""Task domain model — exactly the approved fields, no extras."""

import datetime

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import TaskPriority, TaskStatus
from app.models.mixins import TimestampMixin


class Task(TimestampMixin, Base):
    """A task per the approved product model.

    Required: title, priority, status.
    Optional: description, assignee (zero or one), due date.

    title/description use TEXT storage: this is a purely technical
    storage choice — no unapproved length limits are imposed as product
    validation rules.
    """

    __tablename__ = "tasks"
    __table_args__ = (
        # Database-layer enforcement of the approved value sets; the ORM
        # Enum types validate application-side as well.
        CheckConstraint(
            "status IN ('to_do', 'in_progress', 'review', 'done')",
            name="status_values",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high')",
            name="priority_values",
        ),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Zero or one assignee; NULL means unassigned.
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_tasks_assignee_id_users", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    priority: Mapped[TaskPriority] = mapped_column(
        # Persist the approved VALUES ("low"/"medium"/"high").
        Enum(
            TaskPriority,
            native_enum=False,
            length=16,
            validate_strings=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
    )
    status: Mapped[TaskStatus] = mapped_column(
        # Persist the approved VALUES ("to_do"/"in_progress"/"review"/"done").
        Enum(
            TaskStatus,
            native_enum=False,
            length=16,
            validate_strings=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
    )

    due_date: Mapped[datetime.date | None] = mapped_column(Date(), nullable=True)

    assignee = relationship(
        "User",
        back_populates="tasks",
        foreign_keys=[assignee_id],
    )
    comments = relationship(
        "Comment",
        back_populates="task",
        foreign_keys="Comment.task_id",
        cascade="all, delete-orphan",
    )
