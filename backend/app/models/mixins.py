"""Shared model mixins and base columns."""

import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

# Server-managed timestamps: client input can never set these directly.


class TimestampMixin:
    """created_at / updated_at maintained by the database server."""

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


def utcnow() -> datetime.datetime:
    """Naive UTC timestamp for Python-side defaults (tests, factories)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
