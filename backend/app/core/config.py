"""Central application settings.

All values come from environment variables (12-factor). No secrets are
hardcoded. Security-relevant lifetimes/thresholds are configuration, not
code policy: production values must be supplied by deployment
configuration and are NOT invented here.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Typed application settings loaded from the environment."""

    PROJECT_NAME: str = "Task Management MVP"
    ENVIRONMENT: Literal["local", "development", "production"] = "local"

    # --- Database (MySQL) ---------------------------------------------
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_DB: str = "taskdb"
    MYSQL_USER: str = "appuser"
    MYSQL_PASSWORD: str = ""  # provided via env only — never committed

    # --- HTTP server ---------------------------------------------------
    BACKEND_PORT: int = 8000

    # --- Sessions / cookies (Phase 3A) ----------------------------------
    # Cookie NAME is configuration, not product behavior. The value below
    # is the local/test default; production naming is a deployment
    # decision and stays overridable via environment.
    SESSION_COOKIE_NAME: str = "session"

    # Session lifetime in seconds. REQUIRED for session creation: there
    # is deliberately NO fallback value — an unset/invalid lifetime is a
    # configuration error and session creation fails closed. Production
    # policy values are deployment decisions, not code defaults.
    SESSION_LIFETIME_SECONDS: int | None = None

    # --- Login rate limiting (Phase 3A) ---------------------------------
    # Threshold/window are CONFIGURATION DECISIONS. No permanent
    # production values are established here; deployment must set them.
    # Tests inject explicit test-only values.
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int | None = None
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int | None = None

    # --- CORS (Phase 3A) -------------------------------------------------
    # Production posture: same-origin preferred. Explicit trusted origins
    # only; credentialed wildcard is prohibited by design (the CORSMiddleware
    # wiring rejects '*' whenever credentials are allowed).
    CORS_ALLOWED_ORIGINS_RAW: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "case_sensitive": True,
    }

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Parsed explicit origin allowlist ('' → empty)."""
        return [
            o.strip()
            for o in self.CORS_ALLOWED_ORIGINS_RAW.split(",")
            if o.strip()
        ]

    @property
    def cookie_secure(self) -> bool:
        """Secure attribute: required in production, off locally."""
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()


settings = get_settings()
