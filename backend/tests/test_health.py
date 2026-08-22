"""Phase 1 smoke tests: health + meta endpoints."""

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    """/api/health returns 200 with status ok."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_meta_reports_foundation_phase(client: TestClient) -> None:
    """/api/meta reports service metadata without secrets."""
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert body["phase"] == "foundation"
    assert body["environment"] in {"local", "development", "production"}
    # No secrets may ever appear in metadata responses.
    assert not any("password" in key.lower() for key in body)


def test_unknown_route_returns_404(client: TestClient) -> None:
    """Unknown routes 404."""
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
