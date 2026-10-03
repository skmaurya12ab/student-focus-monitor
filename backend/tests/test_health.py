"""Test backend health endpoint."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_returns_200_and_status_ok():
    """Verify that GET /api/health returns HTTP 200 and {'status': 'ok'}."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_endpoint():
    """Verify that GET / returns HTTP 200 with service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "health" in data
