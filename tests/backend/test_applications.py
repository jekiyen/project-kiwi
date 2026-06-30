"""Tests for the application tracker endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _sa_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from backend.database.models import Application, ApplicationStatus, Job


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _override_db():
    """Replace the DB engine with a fresh in-memory SQLite for every test."""
    from backend.main import app
    from backend.database.session import get_session

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
    """Insert one Job and return its id."""
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


@pytest.fixture
def seeded_jobs(_override_db) -> list[int]:
    """Insert three jobs and return their ids."""
    ids = []
    with Session(_override_db) as s:
        for i in range(3):
            job = Job(
                external_id=f"test-{i:03d}",
                source="seek",
                title=f"Job {i}",
                employer="Test Co",
                location="Auckland",
                url=f"https://seek.co.nz/job/{i}",
            )
            s.add(job)
            s.commit()
            s.refresh(job)
            ids.append(job.id)
    return ids


# ── Save / Apply shortcuts ────────────────────────────────────────────────────

def test_save_job_creates_saved_application(client, seeded_job):
    r = client.post(f"/api/v1/jobs/{seeded_job}/save")
    assert r.status_code == 200
    assert r.json()["status"] == "saved"
    assert r.json()["job_id"] == seeded_job


def test_save_job_idempotent(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/save")
    r = client.post(f"/api/v1/jobs/{seeded_job}/save")
    assert r.status_code == 200
    assert r.json()["status"] == "saved"


def test_apply_job_creates_applied_application(client, seeded_job):
    r = client.post(f"/api/v1/jobs/{seeded_job}/apply")
    assert r.status_code == 200
    assert r.json()["status"] == "applied"
    assert r.json()["applied_at"] is not None


def test_apply_job_over_saved_upgrades_status(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/save")
    r = client.post(f"/api/v1/jobs/{seeded_job}/apply")
    assert r.status_code == 200
    assert r.json()["status"] == "applied"


def test_save_nonexistent_job_returns_404(client):
    r = client.post("/api/v1/jobs/99999/save")
    assert r.status_code == 404


def test_apply_nonexistent_job_returns_404(client):
    r = client.post("/api/v1/jobs/99999/apply")
    assert r.status_code == 404


# ── CRUD ──────────────────────────────────────────────────────────────────────

def test_list_applications_empty(client):
    r = client.get("/api/v1/applications/")
    assert r.status_code == 200
    assert r.json() == []


def test_create_and_list_application(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/save")
    r = client.get("/api/v1/applications/")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["job_title"] == "Packhouse Worker"


def test_create_duplicate_application_returns_409(client, seeded_job):
    client.post("/api/v1/applications/", params={"job_id": seeded_job})
    r = client.post("/api/v1/applications/", params={"job_id": seeded_job})
    assert r.status_code == 409


def test_patch_status(client, seeded_job):
    save_r = client.post(f"/api/v1/jobs/{seeded_job}/save")
    app_id = save_r.json()["id"]
    r = client.patch(f"/api/v1/applications/{app_id}", json={"status": "interview"})
    assert r.status_code == 200
    assert r.json()["status"] == "interview"


def test_patch_notes(client, seeded_job):
    save_r = client.post(f"/api/v1/jobs/{seeded_job}/save")
    app_id = save_r.json()["id"]
    r = client.patch(f"/api/v1/applications/{app_id}", json={"notes": "Looks great!"})
    assert r.status_code == 200
    assert r.json()["notes"] == "Looks great!"


def test_patch_nonexistent_returns_404(client):
    r = client.patch("/api/v1/applications/99999", json={"status": "applied"})
    assert r.status_code == 404


def test_delete_application(client, seeded_job):
    save_r = client.post(f"/api/v1/jobs/{seeded_job}/save")
    app_id = save_r.json()["id"]
    r = client.delete(f"/api/v1/applications/{app_id}")
    assert r.status_code == 204
    assert client.get("/api/v1/applications/").json() == []


def test_delete_nonexistent_returns_404(client):
    r = client.delete("/api/v1/applications/99999")
    assert r.status_code == 404


# ── Pipeline ──────────────────────────────────────────────────────────────────

def test_pipeline_empty(client):
    r = client.get("/api/v1/applications/pipeline")
    assert r.status_code == 200
    data = r.json()
    assert data["saved"] == 0
    assert data["total"] == 0


def test_pipeline_counts(client, seeded_jobs):
    job_a, job_b, job_c = seeded_jobs
    client.post(f"/api/v1/jobs/{job_a}/save")
    client.post(f"/api/v1/jobs/{job_b}/apply")
    client.post(f"/api/v1/jobs/{job_c}/apply")

    r = client.get("/api/v1/applications/pipeline")
    data = r.json()
    assert data["saved"] == 1
    assert data["applied"] == 2
    assert data["total"] == 3


# ── Filter / search ───────────────────────────────────────────────────────────

def test_filter_by_status(client, seeded_jobs):
    job_a, job_b, _ = seeded_jobs
    client.post(f"/api/v1/jobs/{job_a}/save")
    client.post(f"/api/v1/jobs/{job_b}/apply")

    r = client.get("/api/v1/applications/?status=saved")
    assert len(r.json()) == 1
    assert r.json()[0]["status"] == "saved"
