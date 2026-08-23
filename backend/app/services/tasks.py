"""Task service layer (Phase 4A).

Centralizes task business logic ON TOP OF the Phase 3B authorization
policies (which remain the ONLY place role rules live). Routes stay
thin: parse → delegate → serialize.

Errors raised here:
  - :class:`TaskNotFound`      → route maps to HTTP 404
  - :class:`InvalidAssignee`   → route maps to sanitized HTTP 400
  - AuthorizationDenied        → centralized FastAPI handler → HTTP 403

All decisions derive from SERVER-LOADED data: the authenticated user
and the fetched Task row. Client-supplied ownership/assignment claims
are never consulted. There are NO status-transition rules anywhere.
"""

from sqlalchemy.orm import Session

from app.auth import authorization
from app.models import Task, User
from app.schemas.task import TaskCreateRequest, TaskUpdateRequest


class TaskNotFound(Exception):
    """Requested task does not exist (HTTP 404)."""


class InvalidAssignee(Exception):
    """assignee_id does not reference an existing user (HTTP 400)."""


def _load_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise TaskNotFound()
    return task


def _validate_assignee(db: Session, assignee_id: int | None) -> None:
    """An explicit non-null assignee must reference an existing user."""
    if assignee_id is not None and db.get(User, assignee_id) is None:
        raise InvalidAssignee()


def list_tasks(db: Session, user: User) -> list[Task]:
    """Both approved roles may list tasks."""
    authorization.can_view_task(user)
    return list(db.query(Task).order_by(Task.id).all())


def get_task(db: Session, user: User, task_id: int) -> Task:
    """Both approved roles may view a task; missing → TaskNotFound."""
    authorization.can_view_task(user)
    return _load_task(db, task_id)


def create_task(db: Session, user: User, payload: TaskCreateRequest) -> Task:
    """PM only. Identity/timestamps are server-managed."""
    authorization.can_create_task(user)
    _validate_assignee(db, payload.assignee_id)
    task = Task(
        title=payload.title,
        description=payload.description,
        assignee_id=payload.assignee_id,
        priority=payload.priority,
        status=payload.status,
        due_date=payload.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(
    db: Session, user: User, task_id: int, payload: TaskUpdateRequest
) -> Task:
    """PM-only GENERAL edit (title/description/assignee/priority/status/
    due date, partial). Developers are rejected by policy even for a
    status-only payload — the dedicated status endpoint is their only
    path."""
    authorization.can_update_task(user)
    task = _load_task(db, task_id)

    changes = payload.model_dump(exclude_unset=True)
    if "assignee_id" in changes:
        # Explicit null unassigns; non-null must reference a real user.
        _validate_assignee(db, changes["assignee_id"])
    for field, value in changes.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


def update_task_status(
    db: Session, user: User, task_id: int, new_status
) -> Task:
    """Assignment-aware status change (PM always; developer only on OWN
    assigned task). Transition direction is deliberately unrestricted."""
    task = _load_task(db, task_id)
    authorization.can_update_task_status(user, task)
    task.status = new_status
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, user: User, task_id: int) -> None:
    """PM only. Uses the approved cascade behavior (comments die with
    the task via the existing relationship); no soft-delete."""
    authorization.can_delete_task(user)
    task = _load_task(db, task_id)
    db.delete(task)
    db.commit()
