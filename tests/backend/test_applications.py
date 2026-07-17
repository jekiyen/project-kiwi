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


# ── Resume / cover letter versions ─────────────────────────────────────────────

def test_patch_resume_and_cover_letter_version(client, seeded_job):
    save_r = client.post(f"/api/v1/jobs/{seeded_job}/save")
    app_id = save_r.json()["id"]
    r = client.patch(
        f"/api/v1/applications/{app_id}",
        json={"resume_version": "resume_v2_warehouse.pdf", "cover_letter_version": "cl_seek.docx"},
    )
    assert r.status_code == 200
    assert r.json()["resume_version"] == "resume_v2_warehouse.pdf"
    assert r.json()["cover_letter_version"] == "cl_seek.docx"


def test_list_applications_includes_resume_fields(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/save")
    r = client.get("/api/v1/applications/")
    assert r.json()[0]["resume_version"] is None
    assert r.json()[0]["cover_letter_version"] is None


# ── Timeline / history ──────────────────────────────────────────────────────────

def test_timeline_logs_creation_on_save(client, seeded_job):
    save_r = client.post(f"/api/v1/jobs/{seeded_job}/save")
    app_id = save_r.json()["id"]
    r = client.get(f"/api/v1/applications/{app_id}/timeline")
    assert r.status_code == 200
    events = r.json()
    assert len(events) == 1
    assert events[0]["event_type"] == "created"
    assert events[0]["to_status"] == "saved"


def test_timeline_logs_creation_on_apply(client, seeded_job):
    apply_r = client.post(f"/api/v1/jobs/{seeded_job}/apply")
    app_id = apply_r.json()["id"]
    events = client.get(f"/api/v1/applications/{app_id}/timeline").json()
    assert len(events) == 1
    assert events[0]["event_type"] == "created"
    assert events[0]["to_status"] == "applied"


def test_timeline_logs_status_change_on_apply_over_saved(client, seeded_job):
    save_r = client.post(f"/api/v1/jobs/{seeded_job}/save")
    app_id = save_r.json()["id"]
    client.post(f"/api/v1/jobs/{seeded_job}/apply")

    events = client.get(f"/api/v1/applications/{app_id}/timeline").json()
    assert [e["event_type"] for e in events] == ["created", "status_change"]
    assert events[1]["from_status"] == "saved"
    assert events[1]["to_status"] == "applied"


def test_timeline_logs_status_change_on_patch(client, seeded_job):
    save_r = client.post(f"/api/v1/jobs/{seeded_job}/save")
    app_id = save_r.json()["id"]
    client.patch(f"/api/v1/applications/{app_id}", json={"status": "interview"})

    events = client.get(f"/api/v1/applications/{app_id}/timeline").json()
    assert [e["event_type"] for e in events] == ["created", "status_change"]
    assert events[1]["from_status"] == "saved"
    assert events[1]["to_status"] == "interview"


def test_timeline_no_duplicate_event_on_patch_same_status(client, seeded_job):
    save_r = client.post(f"/api/v1/jobs/{seeded_job}/save")
    app_id = save_r.json()["id"]
    client.patch(f"/api/v1/applications/{app_id}", json={"status": "saved"})

    events = client.get(f"/api/v1/applications/{app_id}/timeline").json()
    assert len(events) == 1


def test_timeline_logs_creation_on_direct_post(client, seeded_job):
    create_r = client.post("/api/v1/applications/", params={"job_id": seeded_job})
    app_id = create_r.json()["id"]
    events = client.get(f"/api/v1/applications/{app_id}/timeline").json()
    assert len(events) == 1
    assert events[0]["event_type"] == "created"


def test_timeline_nonexistent_application_returns_404(client):
    r = client.get("/api/v1/applications/99999/timeline")
    assert r.status_code == 404


def test_delete_application_removes_its_timeline_events(client, seeded_job):
    save_r = client.post(f"/api/v1/jobs/{seeded_job}/save")
    app_id = save_r.json()["id"]
    client.delete(f"/api/v1/applications/{app_id}")

    # A fresh application may reuse the deleted row's id (SQLite rowid reuse
    # on an empty table) — its timeline must not inherit the old app's events.
    new_r = client.post(f"/api/v1/jobs/{seeded_job}/save")
    new_app_id = new_r.json()["id"]
    events = client.get(f"/api/v1/applications/{new_app_id}/timeline").json()
    assert len(events) == 1


def test_delete_application_removes_its_application_sessions(client, seeded_job):
    """Phase 8 — an Application Session points at application_id; deleting
    the application must not leave an orphaned session behind."""
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    app_id = client.get(f"/api/v1/jobs/{seeded_job}/application-kit").json()["application"]["id"]

    r = client.delete(f"/api/v1/applications/{app_id}")
    assert r.status_code == 204

    # Re-launching after the application (and its session) were deleted must
    # start a brand new session — not resume a stale orphaned one, which
    # would happen if the old ApplicationSession row had been left behind
    # (SQLite may reuse the deleted application's rowid on an empty table).
    relaunch = client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    new_app_id = relaunch.json()["application"]["id"]
    events = client.get(f"/api/v1/applications/{new_app_id}/timeline").json()
    event_types = [e["event_type"] for e in events]
    assert "session_started" in event_types
    assert "session_resumed" not in event_types
