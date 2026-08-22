"""Central application settings.

All values come from environment variables (12-factor). No secrets are
hardcoded. In Phase 1 these are scaffolding for later phases; nothing here
authenticates or stores credentials yet.
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

    # Reserved for later phases (Phase 3+): session/CSRF configuration.
    # Real secrets must come exclusively from the environment.
    SESSION_COOKIE_NAME: str = "session"
    RATE_LIMIT_LOGIN_MAX_ATTEMPTS: int = 10  # configurable threshold

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "case_sensitive": True,
    }


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()


settings = get_settings()
