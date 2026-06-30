from fastapi.testclient import TestClient

from backend.main import app


def test_health_returns_ok():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "Project Kiwi"
    assert "timestamp" in body
