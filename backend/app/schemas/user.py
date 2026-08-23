"""Phase 5B prerequisite: user directory schemas.

The response is the JSON ARRAY directly: list[UserDirectoryEntry].
Each entry exposes EXACTLY {id, email, role} with ``extra="forbid"``;
anything else (password_hash, timestamps, session/security state, ORM
internals) is structurally excluded.
"""

from pydantic import BaseModel, ConfigDict

from app.models import UserRole


class UserDirectoryEntry(BaseModel):
    """One directory entry: exactly {id, email, role}."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    email: str
    role: UserRole
