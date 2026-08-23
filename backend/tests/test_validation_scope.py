"""Scoped HTTP-400 contract + sanitization tests.

Approved rule: unknown/undeclared fields on MUTATING requests → 400.
Unrelated validation failures keep FastAPI's normal semantics (422).
Both response shapes must be sanitized (never echo submitted values).
"""

from fastapi.testclient import TestClient

from app.main import create_app


def test_unknown_field_on_mutating_request_is_400(api_client: TestClient):
    marker = "SCOPE-MARKER-PASSWORD"
    resp = api_client.post(
        "/api/auth/login",
        json={"email": "a@b.co", "password": marker, "unapproved_field": "admin"},
    )
    assert resp.status_code == 400
    # Submitted VALUES must never be echoed.
    assert marker not in resp.text
    assert "admin" not in resp.text
    assert "a@b.co" not in resp.text


def test_missing_field_keeps_normal_fastapi_semantics(api_client: TestClient):
    """Missing-required-field is NOT an unknown-field case → not forced 400."""
    marker = "SCOPE-MARKER-MISSING"
    resp = api_client.post("/api/auth/login", json={"password": marker})
    assert resp.status_code == 422
    # Sanitized: the submitted password value must not appear.
    assert marker not in resp.text


def test_wrong_type_keeps_normal_fastapi_semantics(api_client: TestClient):
    resp = api_client.post(
        "/api/auth/login", json={"email": 12345, "password": "x"}
    )
    assert resp.status_code == 422
    # Sanitized: the submitted (typed) value must not appear.
    assert "12345" not in resp.text


def test_health_endpoint_unaffected_by_scoping(api_client: TestClient):
    assert api_client.get("/api/health").status_code == 200
