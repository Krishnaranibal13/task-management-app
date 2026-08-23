"""Authentication request/response schemas (strict-input contract).

Mutating request schemas inherit ``StrictModel`` (extra='forbid') so
unknown/undeclared fields are rejected and surfaced as HTTP 400 by the
application exception handler.

Server-controlled values (user id, role, identity, timestamps, session
digests, revocation state) appear in NO request schema.
"""

from pydantic import BaseModel

from app.schemas.base import StrictModel


class LoginRequest(StrictModel):
    """Exactly email + password; nothing else is accepted."""

    email: str
    password: str


class LoginResponse(BaseModel):
    """The session credential is NEVER included — cookie only."""

    csrf_token: str
    token_type: str = "session_cookie"


class LogoutResponse(BaseModel):
    detail: str = "Logged out"


class MeResponse(BaseModel):
    """Non-sensitive identity echo for authenticated probes."""

    user_id: int
    email: str
    role: str
