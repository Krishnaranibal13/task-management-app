"""Phase 4B Comment API routes.

Exactly the two approved endpoints — nothing more:

    GET  /api/tasks/{task_id}/comments   (pm, developer; no CSRF)
    POST /api/tasks/{task_id}/comments   (pm, developer; CSRF required)

Authentication (401) via Phase 3A dependencies; authorization (403) via
the centralized Phase 3B policies called inside the service layer;
missing parent task (404) mapped from the shared service error.
There are NO update/delete/moderation endpoints by design.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as OrmSession

from app.api.deps import map_service_errors
from app.auth.dependencies import get_current_user, require_csrf
from app.db.session import get_db
from app.models import User
from app.schemas.comment import CommentCreateRequest, CommentResponse
from app.services import comments as comment_service

router = APIRouter(prefix="/api/tasks/{task_id}/comments", tags=["comments"])


@router.get("", response_model=list[CommentResponse])
def list_comments(
    task_id: int,
    db: OrmSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    with map_service_errors():
        comments = comment_service.list_comments(db, user, task_id)
    return [CommentResponse.model_validate(c) for c in comments]


@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    payload: CommentCreateRequest,
    task_id: int,
    db: OrmSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: object = Depends(require_csrf),
):
    with map_service_errors():
        comment = comment_service.create_comment(db, user, task_id, payload)
    return CommentResponse.model_validate(comment)
