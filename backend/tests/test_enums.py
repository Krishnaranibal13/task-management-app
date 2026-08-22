"""Approved value-set tests: statuses, priorities, roles."""

import pytest

from app.models import TaskPriority, TaskStatus, UserRole


def test_status_values_exactly_approved() -> None:
    assert {s.value for s in TaskStatus} == {
        "to_do",
        "in_progress",
        "review",
        "done",
    }


def test_priority_values_exactly_approved() -> None:
    assert {p.value for p in TaskPriority} == {"low", "medium", "high"}


def test_role_persisted_values_exactly_pm_and_developer() -> None:
    """Member names stay descriptive; persisted values are pm/developer."""
    assert {r.value for r in UserRole} == {"pm", "developer"}
    assert UserRole.PROJECT_MANAGER.value == "pm"
    assert UserRole.DEVELOPER.value == "developer"


def test_invalid_status_rejected_by_enum() -> None:
    with pytest.raises(ValueError):
        TaskStatus("archived")


def test_invalid_priority_rejected_by_enum() -> None:
    with pytest.raises(ValueError):
        TaskPriority("urgent")


def test_invalid_role_rejected_by_enum() -> None:
    with pytest.raises(ValueError):
        UserRole("admin")


def test_string_values_map_to_enum_members() -> None:
    assert TaskStatus("to_do") is TaskStatus.TO_DO
    assert TaskPriority("high") is TaskPriority.HIGH
    assert UserRole("pm") is UserRole.PROJECT_MANAGER
