"""Approved domain value sets.

Server-side, controlled representations of the approved Task statuses,
priorities, and user roles. These are the ONLY valid values; the database
schema enforces them in addition to application-level validation.

No additional values may be introduced without a human-approved product
change.
"""

import enum


class UserRole(enum.StrEnum):
    """Approved application roles (persisted values are exactly these)."""

    PROJECT_MANAGER = "pm"
    DEVELOPER = "developer"


class TaskStatus(enum.StrEnum):
    """Approved task statuses — exactly these four values."""

    TO_DO = "to_do"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


class TaskPriority(enum.StrEnum):
    """Approved task priorities — exactly these three values."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
