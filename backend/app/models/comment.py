"""Comment domain model — authoritative architecture shape.

Exactly: id, task_id, user_id, content, created_at.
Creation/read only at Product level; no update or delete concept exists,
so there is no updated_at column.
"""

import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Comment(Base):
    """A comment on a task, authored by exactly one user."""

    __tablename__ = "comments"
    __table_args__ = (
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", name="fk_comments_task_id_tasks", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_comments_user_id_users", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Approved shape carries created_at only — no updated_at.
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )

    task = relationship("Task", back_populates="comments", foreign_keys=[task_id])
    author = relationship("User", back_populates="comments", foreign_keys=[user_id])
