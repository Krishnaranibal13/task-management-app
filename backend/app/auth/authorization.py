"""Server-side authorization foundation (Phase 3B).

Centralized, reusable policies implementing the APPROVED product
authorization matrix. Built strictly ON TOP OF the Phase 3A
authentication layer (``get_current_user`` / ``get_current_session``):
authentication answers WHO you are (401 when unknown), authorization
answers WHAT you may do (403 when insufficient).

Approved roles are exactly ``pm`` and ``developer``. Anything else fails
CLOSED: an authenticated identity whose role falls outside the approved
set is granted nothing and every policy denies access.

Security invariants:
  - Decisions derive ONLY from the server-loaded authenticated user and
    the server-loaded task row. Client-supplied role/id/ownership claims
    are never consulted.
  - There are NO status-transition rules anywhere in this module: WHO may
    change status is a policy question; WHICH approved status is chosen
    is not restricted (To Do -> Done etc. remain permitted).
  - No unapproved capabilities (comment edit/delete/moderation/reactions,
    attachments, extra roles, permission tables) exist here.
"""

from app.models.enums import UserRole


class AuthorizationDenied(Exception):
    """Raised when an authenticated identity lacks permission.

    Mapped CENTRALLY by the FastAPI exception handler in
    ``app.main`` to HTTP 403 with a generic sanitized body
    (``{"detail": "Forbidden"}``). Internal reason strings, user/role/
    task identifiers and assignment details never reach the client.

    NOTE: deliberately NOT a frozen dataclass — frozen instances break
    the exception protocol (CPython assigns ``__traceback__`` during
    propagation, which frozen dataclasses forbid).
    """

    def __init__(self, reason: str = "forbidden"):
        super().__init__(reason)
        self.reason = reason


def _approved_roles() -> frozenset[UserRole]:
    return frozenset({UserRole.PROJECT_MANAGER, UserRole.DEVELOPER})


def _role(user) -> UserRole | None:
    """Normalized server-side role of an authenticated identity.

    Accepts either a ``UserRole`` member or its approved persisted value
    ("pm"/"developer") so policies behave identically for ORM rows and
    plain service-layer objects. Anything else normalizes to None and
    FAILS CLOSED everywhere downstream.
    """
    role = getattr(user, "role", None)
    if isinstance(role, UserRole):
        return role
    try:
        return UserRole(role) if role is not None else None
    except (ValueError, TypeError):
        return None


def require_approved_role(user) -> None:
    """Fail closed unless the authenticated user's role is approved.

    Unknown/coerced roles must never be treated as pm or developer.
    """
    if _role(user) not in _approved_roles():
        raise AuthorizationDenied("role_not_permitted")


# --- identity prerequisites ---------------------------------------------


def require_authenticated_user(user) -> None:
    """Defense-in-depth policy prerequisite — NOT the HTTP auth mechanism.

    HTTP authentication (missing/unknown/expired/revoked session → 401)
    is performed exclusively by the Phase 3A dependency
    ``get_current_user``. Authorization functions are meant to receive
    ALREADY-AUTHENTICATED server-side identities; this guard exists only
    so a policy can never be invoked with an anonymous placeholder. A
    ``None`` here raises :class:`AuthorizationDenied` as defensive
    programming, but no production route can reach that path, because
    the request would have failed with HTTP 401 inside
    ``get_current_user`` first.
    """
    if user is None or getattr(user, "id", None) is None:
        raise AuthorizationDenied("authenticated_user_required")
    require_approved_role(user)


# --- PM-only capabilities ------------------------------------------------


def require_pm(user) -> None:
    """PM required."""
    require_authenticated_user(user)
    if _role(user) is not UserRole.PROJECT_MANAGER:
        raise AuthorizationDenied("pm_required")


# --- task viewing ---------------------------------------------------------


def can_view_task(user) -> None:
    """Viewing tasks is allowed for BOTH approved roles."""
    require_authenticated_user(user)


# --- task creation / deletion / general mutation / assignment -------------


def can_create_task(user) -> None:
    """Only PM may create tasks."""
    require_pm(user)


def can_delete_task(user) -> None:
    """Only PM may delete tasks."""
    require_pm(user)


def can_update_task(user) -> None:
    """General task mutation (title/description/priority/due date): PM only."""
    require_pm(user)


def can_assign_task(user) -> None:
    """Assignment/reassignment: PM only."""
    require_pm(user)


# --- status updates (assignment-aware, transition-agnostic) ---------------


def can_update_task_status(user, task) -> None:
    """Status updates per the security-critical assignment rule.

    Allowed when:
      - authenticated PM (regardless of assignee), OR
      - authenticated Developer AND task.assignee_id == user.id
        (server-loaded values only)

    Denied for Developers on unassigned tasks and on tasks assigned to
    someone else. NO transition restrictions exist here by design.
    """
    require_approved_role(user)
    if _role(user) is UserRole.PROJECT_MANAGER:
        return
    # Developer path: ownership must match server-side data exactly.
    assignee_id = getattr(task, "assignee_id", "missing")
    if assignee_id is not None and assignee_id == user.id:
        return
    raise AuthorizationDenied("developer_not_assigned_to_task")


# --- comments --------------------------------------------------------------


def can_add_comment(user) -> None:
    """Both approved roles may add comments."""
    require_authenticated_user(user)
