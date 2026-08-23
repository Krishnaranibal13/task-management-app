"""Phase 5B prerequisite routes: minimal authenticated user directory.

Exactly one endpoint:

    GET /api/users   (pm, developer; safe read → no CSRF)

Returns the JSON ARRAY directly (list[UserDirectoryEntry]) so FastAPI's
response_model validation/serialization stays active. Read-only by
design: no POST/PATCH/PUT/DELETE variants exist.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as OrmSession

from app.api.deps import map_service_errors
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.user import UserDirectoryEntry
from app.services import users as user_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserDirectoryEntry])
def list_users(
    db: OrmSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[UserDirectoryEntry]:
    with map_service_errors():
        entries = [
            UserDirectoryEntry.model_validate(u)
            for u in user_service.list_users(db, user)
        ]
    return entries
