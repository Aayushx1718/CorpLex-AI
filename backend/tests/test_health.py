from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from app.main import app


def test_liveness():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "corplex-api"}


def test_readiness_failure_is_sanitized(monkeypatch):
    def fail():
        raise OperationalError("private connection details", {}, Exception("secret"))
    monkeypatch.setattr("app.main.engine.connect", fail)
    with TestClient(app) as client:
        response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database or schema unavailable"}


def test_cors_allows_frontend():
    with TestClient(app) as client:
        response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
