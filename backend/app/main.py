"""Task Management MVP — FastAPI backend.

Foundation phase: application factory and health endpoint, plus
MySQL/Alembic scaffolding. Authentication, RBAC, and task/comment
features are deliberately NOT implemented in Phase 1.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health
from app.core.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks.

    Never log secrets or credentials — only non-sensitive facts.
    """
    print(f"{settings.PROJECT_NAME} backend starting up", flush=True)
    print(
        f"Environment: {settings.ENVIRONMENT} | "
        f"MySQL host: {settings.MYSQL_HOST}:{settings.MYSQL_PORT} | "
        f"Database name: {settings.MYSQL_DB}",
        flush=True,
    )
    yield


def create_app() -> FastAPI:
    """Application factory for the Task Management MVP backend."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description=(
            "Backend foundation (Phase 1): health endpoint and database "
            "scaffolding. Auth, tasks, and comments arrive in later phases."
        ),
        lifespan=lifespan,
    )

    app.include_router(health.router)

    return app


app = create_app()
