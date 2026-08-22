"""Strict request-schema foundation tests.

Phase 2 keeps only the reusable strictness base (option A of the review):
concrete request schemas are built in their API phases, so no unapproved
validation rules (e.g. text length limits) exist yet.
"""

import pytest
from pydantic import ValidationError

from app.schemas.base import StrictModel


def test_strictness_is_inherited_by_default() -> None:
    class Probe(StrictModel):
        a: int

    with pytest.raises(ValidationError):
        Probe(a=1, b=2)


def test_no_premature_concrete_task_schema() -> None:
    """Concrete schemas arrive with the API phase — none exist yet."""
    import app.schemas.base as base_module

    assert not hasattr(base_module, "TaskCreateBase")


def test_no_length_limit_rules_defined() -> None:
    """Unapproved limits must not be smuggled in as product validation."""
    source = open("app/schemas/base.py", encoding="utf-8").read()
    assert "max_length" not in source
