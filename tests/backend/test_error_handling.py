"""Tests for global error handling and request-ID middleware."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _sa_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

import pytest


@pytest.fixture(autouse=True)
def _override_db():
    from backend.database.session import get_session
    from backend.main import app

    engine = _sa_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _get_session
    yield engine
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client(_override_db):
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def seeded_job(_override_db) -> int:
    from backend.database.models import Job

    with Session(_override_db) as s:
        job = Job(
            external_id="test-001",
            source="seek",
            title="Packhouse Worker",
            employer="Test Co",
            location="Auckland",
            url="https://seek.co.nz/job/1",
        )
        s.add(job)
        s.commit()
        s.refresh(job)
        return job.id


# ── Consistent error shape ───────────────────────────────────────────────────

def test_404_has_consistent_error_shape(client):
    r = client.get("/api/v1/applications/99999/timeline")
    assert r.status_code == 404
    data = r.json()
    assert data["error"] == "http_error"
    assert "message" in data
    assert "detail" not in data  # not FastAPI's default shape


def test_409_has_consistent_error_shape(client, seeded_job):
    client.post("/api/v1/applications/", params={"job_id": seeded_job})
    r = client.post("/api/v1/applications/", params={"job_id": seeded_job})
    assert r.status_code == 409
    assert r.json()["error"] == "http_error"


def test_scan_trigger_409_when_already_running(client, _override_db):
    from backend.database.models import Scan, ScanStatus

    with Session(_override_db) as s:
        s.add(Scan(source="all", status=ScanStatus.RUNNING))
        s.commit()

    r = client.post("/api/v1/scans/trigger")
    assert r.status_code == 409
    assert r.json()["error"] == "http_error"


def test_scan_trigger_202_when_none_running(client, monkeypatch):
    from backend.agents.base import AgentResult
    from backend.agents.scan_agent import ScanAgent

    async def _noop_run(self):
        return AgentResult(success=True, message="noop")

    monkeypatch.setattr(ScanAgent, "run", _noop_run)

    r = client.post("/api/v1/scans/trigger")
    assert r.status_code == 202


def test_validation_error_has_consistent_shape(client):
    r = client.patch("/api/v1/applications/1", json={"status": "not-a-real-status"})
    assert r.status_code == 422
    data = r.json()
    assert data["error"] == "validation_error"
    assert "details" in data


def test_no_stack_trace_leaked_on_validation_error(client):
    r = client.patch("/api/v1/applications/1", json={"status": "not-a-real-status"})
    body = r.text
    assert "Traceback" not in body
    assert ".py\", line" not in body


# ── Request ID ────────────────────────────────────────────────────────────────

def test_response_includes_request_id_header(client):
    r = client.get("/api/v1/health")
    assert "x-request-id" in {k.lower() for k in r.headers.keys()}


def test_request_id_is_echoed_back_when_provided(client):
    r = client.get("/api/v1/health", headers={"X-Request-ID": "test-req-123"})
    assert r.headers["x-request-id"] == "test-req-123"


def test_different_requests_get_different_request_ids(client):
    r1 = client.get("/api/v1/health")
    r2 = client.get("/api/v1/health")
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


# ── Health check ──────────────────────────────────────────────────────────────

def test_health_reports_database_status(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert "WIB" not in data["timestamp"]  # ISO format, not the human display format
