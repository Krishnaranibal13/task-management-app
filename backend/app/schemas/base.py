"""Strict request-schema foundations for later API phases.

Contract (approved security requirements):
  - Mutating request schemas forbid unknown/undeclared fields; violations
    must surface as HTTP 400 at the API layer.
  - Authenticated-user identity and comment authorship are always
    server-derived, never client input.

Concrete request schemas (task create/update, comment create) are built
in their API phases on top of this base — none are pre-defined here, so
no unapproved validation rules exist yet.
"""

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base for all *request* schemas.

    ``extra='forbid'`` rejects undeclared fields with a ValidationError,
    which FastAPI translates to HTTP 422 by default. The API layer will
    register an exception handler mapping this to HTTP 400 per the
    approved security contract.
    """

    model_config = ConfigDict(extra="forbid")
