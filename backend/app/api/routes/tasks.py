"""Phase 4A Task API routes.

Exactly the six approved endpoints — no more:

    GET    /api/tasks              (pm, developer)
    GET    /api/tasks/{task_id}    (pm, developer)
    POST   /api/tasks              (pm,          CSRF required)
    PATCH  /api/tasks/{task_id}    (pm,          CSRF required)
    PATCH  /api/tasks/{task_id}/status (pm or assigned developer, CSRF)
    DELETE /api/tasks/{task_id}    (pm,          CSRF required)

Authentication (401) is enforced by the Phase 3A dependencies;
authorization (403) by the Phase 3B policies via the service layer;
missing tasks (404) map from :class:`services.tasks.TaskNotFound`.
GET endpoints require no CSRF; all mutating ones use the existing
session-bound CSRF dependency.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as OrmSession

from app.api.deps import map_service_errors
from app.auth.dependencies import get_current_user, require_csrf
from app.db.session import get_db
from app.models import User
from app.schemas.task import (
    TaskCreateRequest,
    TaskResponse,
    TaskStatusUpdateRequest,
    TaskUpdateRequest,
)
from app.services import tasks as task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    db: OrmSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    with map_service_errors():
        tasks = task_service.list_tasks(db, user)
    return [TaskResponse.model_validate(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: OrmSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    with map_service_errors():
        task = task_service.get_task(db, user, task_id)
    return TaskResponse.model_validate(task)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreateRequest,
    db: OrmSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: object = Depends(require_csrf),
):
    with map_service_errors():
        task = task_service.create_task(db, user, payload)
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    payload: TaskUpdateRequest,
    db: OrmSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: object = Depends(require_csrf),
):
    with map_service_errors():
        task = task_service.update_task(db, user, task_id, payload)
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}/status", response_model=TaskResponse)
def update_task_status(
    task_id: int,
    payload: TaskStatusUpdateRequest,
    db: OrmSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: object = Depends(require_csrf),
):
    with map_service_errors():
        task = task_service.update_task_status(db, user, task_id, payload.status)
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: OrmSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: object = Depends(require_csrf),
):
    with map_service_errors():
        task_service.delete_task(db, user, task_id)
    return None
