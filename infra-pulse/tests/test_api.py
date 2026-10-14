from fastapi.testclient import TestClient

from app.main import app


def test_api_and_dashboard():
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        health = client.get("/api/health")
        assert health.status_code == 200
        overview = client.get("/api/overview")
        assert overview.status_code == 200
        assert "devices" in overview.json()
        assert client.get("/api/events").status_code == 200
        assert client.get("/api/history").status_code == 200
        assert client.get("/api/history?host=not-configured").status_code == 404
        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert b"infrapulse_system_cpu_percent" in metrics.content
