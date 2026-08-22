"""Pytest configuration.

Phase 1 scope: verify the app imports and the health/meta endpoints
respond. Database-backed tests are added in later phases once models
exist.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    """Test client bound to the FastAPI application."""
    return TestClient(app)
