"""Model registry imported by Alembic ``env.py``.

Phase 1: intentionally empty of concrete models. Concrete models
(users, sessions, tasks, comments) are added in later phases; when they
are, they must be imported here so Alembic autogenerate sees them.
"""

# from app.models.user import User            # noqa: F401  (Phase 3)
# from app.models.session import Session       # noqa: F401  (Phase 3)
# from app.models.task import Task             # noqa: F401  (Phase 2)
# from app.models.comment import Comment       # noqa: F401  (Phase 2)

__all__: list[str] = []
