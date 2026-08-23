"""Phase 4A Task API schemas.

Request schemas extend the approved :class:`StrictModel` (unknown
fields → HTTP 400 via the centralized handler). Response schemas
expose ONLY approved product fields — never ORM internals, security
state, password hashes, or session material.
"""

import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.models import TaskPriority, TaskStatus
from app.schemas.base import StrictModel


class TaskCreateRequest(StrictModel):
    """POST /api/tasks — exactly the approved fields."""

    title: str
    description: str | None = None
    assignee_id: int | None = None
    priority: TaskPriority
    status: TaskStatus
    due_date: datetime.date | None = None


class TaskUpdateRequest(StrictModel):
    """PATCH /api/tasks/{task_id} — true partial PATCH semantics.

    - All approved fields may be OMITTED; omitted fields remain
      unchanged (``exclude_unset`` is used by the service layer).
    - An empty PATCH body ``{}`` remains allowed and is a no-op.
    - REQUIRED product fields must not be EXPLICITLY null:
      title, priority, status → ordinary validation failure (HTTP 422)
      before any database involvement.
    - NULLABLE fields may explicitly be null: description,
      assignee_id (null = PM unassign), due_date.

    Server-managed fields (id/created_at/updated_at/creator identity)
    are not declared at all, so supplying them is an unknown-field 400.
    """

    title: str | None = None
    description: str | None = None
    assignee_id: int | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    due_date: datetime.date | None = None

    @model_validator(mode="after")
    def _required_fields_may_not_be_explicitly_null(self):
        for name in ("title", "priority", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                # Message stays internal: the centralized handler returns
                # only locations + a generic label to the client.
                raise ValueError(f"'{name}' must not be null")
        return self


class TaskStatusUpdateRequest(StrictModel):
    """PATCH /api/tasks/{task_id}/status — EXACTLY {status}."""

    status: TaskStatus


class TaskResponse(BaseModel):
    """Approved product view of a task. Internal/security state is
    structurally excluded."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    assignee_id: int | None
    priority: TaskPriority
    status: TaskStatus
    due_date: datetime.date | None
