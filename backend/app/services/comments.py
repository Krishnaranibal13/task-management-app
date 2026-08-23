"""Comment service layer (Phase 4B).

Thin, centralized comment business logic ON TOP OF the Phase 3B
authorization policies. Routes stay thin; role rules live only in
``app/auth/authorization.py``.

Server-controlled invariants:
  - The parent Task is loaded FROM THE URL task_id; a missing task is
    :class:`TaskNotFound` → HTTP 404 (never 403).
  - The author is ALWAYS ``authenticated_user.id`` — client-supplied
    identity claims are never consulted.
  - Listing/creation are permitted for BOTH approved roles; no invented
    assignment restriction applies to comments.

Errors:
  - TaskNotFound (reused from the task service) → HTTP 404
"""

from sqlalchemy.orm import Session

from app.auth import authorization
from app.models import Comment, Task, User
from app.schemas.comment import CommentCreateRequest
from app.services.tasks import TaskNotFound


def _load_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise TaskNotFound()
    return task


def list_comments(db: Session, user: User, task_id: int) -> list[Comment]:
    """Both approved roles may list comments of an existing task."""
    authorization.can_view_task(user)
    task = _load_task(db, task_id)
    return (
        db.query(Comment)
        .filter(Comment.task_id == task.id)
        .order_by(Comment.created_at, Comment.id)
        .all()
    )


def create_comment(
    db: Session, user: User, task_id: int, payload: CommentCreateRequest
) -> Comment:
    """Both approved roles may comment on ANY existing task.

    Author = authenticated_user.id (server-side), never client input.
    """
    authorization.can_add_comment(user)
    task = _load_task(db, task_id)
    comment = Comment(
        task_id=task.id,
        user_id=user.id,
        content=payload.content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment
