"""Task Management MVP — FastAPI backend.

Phase 3A adds authentication infrastructure: Argon2id login, MySQL-backed
server sessions, session-bound CSRF synchronizer tokens, logout/revocation,
optional rate limiting, and strict-input handling.

Not yet implemented (later phases): RBAC enforcement, task/comment APIs,
frontend features.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health
from app.auth.routes import router as auth_router
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
            "Backend foundation: health endpoint; Phase 3A authentication "
            "infrastructure (login/logout, server sessions, CSRF). Task "
            "and comment APIs arrive in later phases."
        ),
        lifespan=lifespan,
    )

    # --- CORS -----------------------------------------------------------
    # Approved posture: same-origin preferred; explicit trusted origins
    # only; credentialed wildcard prohibited by construction.
    origins = settings.cors_allowed_origins
    if "*" in origins:
        raise RuntimeError(
            "CORS misconfiguration: wildcard origin is prohibited "
            "(credentialed wildcard CORS is not allowed)."
        )
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["X-CSRF-Token"],
        )

    # --- Strict input contract ------------------------------------------
    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        """Sanitized validation responses with SCOPED status codes.

        Approved contract: unknown/undeclared fields on MUTATING requests
        (POST/PUT/PATCH/DELETE) → HTTP 400. Unrelated request-validation
        failures (missing fields, wrong types, …) keep FastAPI's normal
        semantics (HTTP 422).

        Both shapes are SANITIZED: only field locations and a generic
        error label are returned. Pydantic's raw error payloads embed the
        submitted ``input`` values (e.g. passwords) and are never echoed.
        """
        errors = exc.errors()
        has_extra_forbidden = any(e.get("type") == "extra_forbidden" for e in errors)
        is_mutating = request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
        status_code = 400 if (is_mutating and has_extra_forbidden) else 422
        return JSONResponse(
            status_code=status_code,
            content={
                "detail": [
                    {"loc": list(e.get("loc", [])), "error": "invalid_input"}
                    for e in errors
                ]
            },
        )

    app.include_router(health.router)
    app.include_router(auth_router)

    return app


app = create_app()
