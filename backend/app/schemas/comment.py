"""Phase 4B Comment API schemas.

Request schema extends the approved :class:`StrictModel` (unknown
fields → HTTP 400 via the centralized handler). The response exposes
ONLY the approved Comment fields — never user profiles, security
state, or ORM internals.
"""

import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.base import StrictModel


class CommentCreateRequest(StrictModel):
    """POST /api/tasks/{task_id}/comments — exactly {content}.

    ``content`` is required; explicit ``null`` is an ordinary validation
    failure (HTTP 422) before any database involvement. Identity fields
    (id/task_id/user_id/author_id/created_at/role) are NOT declared, so
    supplying them is an unknown-field 400. No length limits are imposed
    beyond the approved contract.
    """

    content: str


class CommentResponse(BaseModel):
    """Approved product view of a comment."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    user_id: int
    content: str
    created_at: datetime.datetime
