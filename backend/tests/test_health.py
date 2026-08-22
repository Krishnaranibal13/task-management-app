"""Phase 1 smoke tests: health endpoint only."""

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    """/api/health returns 200 with status ok."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_meta_endpoint_removed(client: TestClient) -> None:
    """/api/meta must NOT exist: not part of the approved MVP surface."""
    resp = client.get("/api/meta")
    assert resp.status_code == 404


def test_unknown_route_returns_404(client: TestClient) -> None:
    """Unknown routes 404."""
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
