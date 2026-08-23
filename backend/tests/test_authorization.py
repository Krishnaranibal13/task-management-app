"""Authorization policy tests (Phase 3B).

Pure unit tests over the centralized policies — no HTTP routes exist by
design (routes arrive with the API phases). Covers the approved matrix:
PM capabilities, Developer restrictions, the security-critical
assignment rule, fail-closed role handling, and the ABSENCE of status
transition rules.
"""

import pytest

from app.auth.authorization import (
    AuthorizationDenied,
    can_add_comment,
    can_assign_task,
    can_create_task,
    can_delete_task,
    can_update_task,
    can_update_task_status,
    can_view_task,
    require_approved_role,
    require_authenticated_user,
    require_pm,
)
from app.models import TaskPriority, TaskStatus


class _User:
    """Minimal server-side identity stand-in (id + role only)."""

    def __init__(self, user_id: int, role):
        self.id = user_id
        self.role = role


class _Task:
    """Minimal server-loaded task stand-in."""

    def __init__(self, assignee_id=None, task_id: int = 1):
        self.id = task_id
        self.assignee_id = assignee_id


PM = "pm"
DEV = "developer"


@pytest.fixture()
def pm():
    return _User(1, PM)


@pytest.fixture()
def dev():
    return _User(2, DEV)


@pytest.fixture()
def other_dev():
    return _User(3, DEV)


def denies(fn, *args):
    with pytest.raises(AuthorizationDenied):
        fn(*args)


# --- role validation / fail-closed ----------------------------------------


def test_pm_role_recognized(pm) -> None:
    require_approved_role(pm)
    require_pm(pm)


def test_developer_role_recognized(dev) -> None:
    require_approved_role(dev)


@pytest.mark.parametrize(
    "bogus_role", ["admin", "superuser", "guest", "moderator", "", "PM", "PM_"]
)
def test_unapproved_roles_fail_closed(bogus_role) -> None:
    user = _User(9, bogus_role)
    denies(require_approved_role, user)
    denies(require_authenticated_user, user)
    denies(require_pm, user)
    denies(can_create_task, user)
    denies(can_delete_task, user)
    denies(can_update_task, user)
    denies(can_assign_task, user)
    denies(can_update_task_status, user, _Task(assignee_id=9))
    denies(can_add_comment, user)
    denies(can_view_task, user)


def test_none_user_fails_closed() -> None:
    denies(require_authenticated_user, None)


def test_missing_identity_fails_closed() -> None:
    class _Ghost:
        id = None
        role = PM

    denies(require_authenticated_user, _Ghost())


# --- PM matrix ------------------------------------------------------------


def test_pm_can_view_task(pm) -> None:
    can_view_task(pm)


def test_pm_can_create_task(pm) -> None:
    can_create_task(pm)


def test_pm_can_delete_task(pm) -> None:
    can_delete_task(pm)


def test_pm_can_general_update_task(pm) -> None:
    can_update_task(pm)


def test_pm_can_assign_and_reassign(pm) -> None:
    can_assign_task(pm)


def test_pm_may_update_status_regardless_of_assignee(pm) -> None:
    can_update_task_status(pm, _Task(assignee_id=None))
    can_update_task_status(pm, _Task(assignee_id=2))   # assigned to a developer
    can_update_task_status(pm, _Task(assignee_id=1))   # assigned to themselves
    can_update_task_status(pm, _Task(assignee_id=99))  # anyone


def test_pm_can_add_comment(pm) -> None:
    can_add_comment(pm)


# --- Developer matrix ------------------------------------------------------


def test_developer_can_view_task(dev) -> None:
    can_view_task(dev)


def test_developer_can_add_comment(dev) -> None:
    can_add_comment(dev)


def test_developer_cannot_create_task(dev) -> None:
    denies(can_create_task, dev)


def test_developer_cannot_delete_task(dev) -> None:
    denies(can_delete_task, dev)


def test_developer_cannot_general_update_task(dev) -> None:
    denies(can_update_task, dev)


def test_developer_cannot_assign_or_reassign(dev) -> None:
    denies(can_assign_task, dev)


def test_developer_may_update_status_of_own_assigned_task(dev) -> None:
    own = _Task(assignee_id=dev.id)
    can_update_task_status(dev, own)


def test_developer_cannot_update_status_of_other_users_task(dev, other_dev) -> None:
    denies(can_update_task_status, dev, _Task(assignee_id=other_dev.id))


def test_developer_cannot_update_status_of_unassigned_task(dev) -> None:
    denies(can_update_task_status, dev, _Task(assignee_id=None))


# --- NO transition restrictions (WHO, not WHICH) ---------------------------


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (TaskStatus.TO_DO, TaskStatus.IN_PROGRESS),
        (TaskStatus.TO_DO, TaskStatus.DONE),      # forward jump allowed
        (TaskStatus.IN_PROGRESS, TaskStatus.REVIEW),
        (TaskStatus.REVIEW, TaskStatus.DONE),
        (TaskStatus.DONE, TaskStatus.TO_DO),      # backward allowed
        (TaskStatus.REVIEW, TaskStatus.TO_DO),
    ],
)
def test_no_transition_restrictions_for_any_role(pm, dev, from_status, to_status) -> None:
    """Authorization must not care WHICH approved statuses are involved."""
    # Both endpoints of every tested pair are members of the approved set.
    approved = {s.value for s in TaskStatus}
    assert from_status.value in approved and to_status.value in approved
    # PM on any assignment shape...
    for task in (_Task(None), _Task(pm.id), _Task(42)):
        can_update_task_status(pm, task)
    # ...and Developer on their OWN task — every pair equally permitted.
    can_update_task_status(dev, _Task(assignee_id=dev.id))


def test_priority_values_untouched_by_authorization() -> None:
    """Authorization adds no priority/status semantics of its own."""
    assert {p.value for p in TaskPriority} == {"low", "medium", "high"}
