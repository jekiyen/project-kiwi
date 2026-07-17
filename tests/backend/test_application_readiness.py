"""Tests for the Application Readiness Engine (backend/core/application_readiness.py)
— the evaluator itself, and the Application Copilot endpoints that consume
it (GET /jobs/{id}/application-readiness, GET /jobs/readiness-summary,
GET /jobs/{id}/application-kit). See docs/ROADMAP.md Phase 8.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _sa_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from backend.core.application_readiness import (
    ApplicationReadinessStatus,
    evaluate_application_readiness,
)
from backend.database.models import ApplicationProfile, ApplicationReference, Job, Resume


def make_job(**overrides) -> Job:
    defaults = dict(
        external_id="test-001",
        source="seek",
        title="Packhouse Worker",
        employer="Test Co",
        location="Auckland",
        description="Pack fruit at a busy packhouse.",
        url="https://seek.co.nz/job/1",
    )
    defaults.update(overrides)
    return Job(**defaults)


def make_resume(**overrides) -> Resume:
    defaults = dict(
        original_filename="cv.pdf",
        stored_filename="uuid-cv.pdf",
        filename="My Resume.pdf",
        file_type="pdf",
        file_size=1234,
        is_active=True,
    )
    defaults.update(overrides)
    return Resume(**defaults)


def make_filled_profile(**overrides) -> ApplicationProfile:
    defaults = dict(
        full_name="Rizky Aditya",
        email="rizky@example.com",
        phone="+62 812 0000 0000",
        visa_status="None",
        driver_license=True,
    )
    defaults.update(overrides)
    return ApplicationProfile(**defaults)


# ── evaluate_application_readiness — unit tests ─────────────────────────────

def test_not_ready_when_resume_missing():
    result = evaluate_application_readiness(make_job(), make_filled_profile(), [], None)
    assert result.status == ApplicationReadinessStatus.NOT_READY
    assert "Resume" in result.missing


def test_not_ready_when_profile_missing_entirely():
    result = evaluate_application_readiness(make_job(), None, [], make_resume())
    assert result.status == ApplicationReadinessStatus.NOT_READY
    assert "Application Profile" in result.missing


def test_not_ready_when_profile_exists_but_completely_blank():
    """A lazily-created empty singleton profile doesn't count as filled in."""
    blank = ApplicationProfile()
    result = evaluate_application_readiness(make_job(), blank, [], make_resume())
    assert result.status == ApplicationReadinessStatus.NOT_READY
    assert "Application Profile" in result.missing


def test_not_ready_takes_priority_over_partial():
    result = evaluate_application_readiness(make_job(), None, [], None)
    assert result.status == ApplicationReadinessStatus.NOT_READY
    assert set(result.missing) >= {"Resume", "Application Profile"}


def test_partial_when_cover_letter_missing():
    profile = make_filled_profile()
    refs = [ApplicationReference(profile_id=1, name="Jane Doe")]
    result = evaluate_application_readiness(make_job(), profile, refs, make_resume())
    assert result.status == ApplicationReadinessStatus.PARTIAL
    assert "Cover Letter" in result.missing


def test_partial_when_references_missing():
    profile = make_filled_profile()
    result = evaluate_application_readiness(
        make_job(cover_letter_generated_at=__import__("datetime").datetime.utcnow()),
        profile, [], make_resume(),
    )
    assert result.status == ApplicationReadinessStatus.PARTIAL
    assert "Reference" in result.missing


def test_partial_when_phone_missing():
    from datetime import datetime
    profile = make_filled_profile(phone=None)
    refs = [ApplicationReference(profile_id=1, name="Jane Doe")]
    result = evaluate_application_readiness(
        make_job(cover_letter_generated_at=datetime.utcnow()), profile, refs, make_resume()
    )
    assert result.status == ApplicationReadinessStatus.PARTIAL
    assert "Phone Number" in result.missing


def test_partial_when_driver_license_false():
    from datetime import datetime
    profile = make_filled_profile(driver_license=False)
    refs = [ApplicationReference(profile_id=1, name="Jane Doe")]
    result = evaluate_application_readiness(
        make_job(cover_letter_generated_at=datetime.utcnow()), profile, refs, make_resume()
    )
    assert result.status == ApplicationReadinessStatus.PARTIAL
    assert "Driver License" in result.missing


def test_partial_when_work_rights_missing():
    from datetime import datetime
    profile = make_filled_profile(visa_status=None, work_rights_current_country=None)
    refs = [ApplicationReference(profile_id=1, name="Jane Doe")]
    result = evaluate_application_readiness(
        make_job(cover_letter_generated_at=datetime.utcnow()), profile, refs, make_resume()
    )
    assert result.status == ApplicationReadinessStatus.PARTIAL
    assert "Work Rights" in result.missing


def test_ready_when_everything_present():
    from datetime import datetime
    profile = make_filled_profile()
    refs = [ApplicationReference(profile_id=1, name="Jane Doe")]
    result = evaluate_application_readiness(
        make_job(cover_letter_generated_at=datetime.utcnow()), profile, refs, make_resume()
    )
    assert result.status == ApplicationReadinessStatus.READY
    assert result.missing == []
    assert result.score == 100


def test_score_and_estimated_minutes_are_deterministic():
    r1 = evaluate_application_readiness(make_job(), None, [], None)
    r2 = evaluate_application_readiness(make_job(), None, [], None)
    assert r1.score == r2.score
    assert r1.estimated_minutes == r2.estimated_minutes
    assert r1.estimated_minutes > 15  # base + hard-item penalties


def test_sections_reflect_individual_readiness():
    from datetime import datetime
    profile = make_filled_profile()
    refs = [ApplicationReference(profile_id=1, name="Jane Doe")]
    result = evaluate_application_readiness(
        make_job(cover_letter_generated_at=datetime.utcnow()), profile, refs, make_resume()
    )
    assert result.sections.resume is True
    assert result.sections.application_profile is True
    assert result.sections.cover_letter is True
    assert result.sections.references is True
    assert result.sections.work_rights is True


# ── API fixtures ─────────────────────────────────────────────────────────────

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
    with Session(_override_db) as s:
        job = make_job()
        s.add(job)
        s.commit()
        s.refresh(job)
        return job.id


def _activate_resume(engine) -> None:
    with Session(engine) as s:
        s.add(make_resume())
        s.commit()


def _fill_profile(engine, **overrides) -> None:
    with Session(engine) as s:
        s.add(make_filled_profile(**overrides))
        s.commit()


# ── GET /jobs/{id}/application-readiness ────────────────────────────────────

def test_readiness_endpoint_not_ready_without_anything(client, seeded_job):
    r = client.get(f"/api/v1/jobs/{seeded_job}/application-readiness")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "not_ready"
    assert "Resume" in data["missing"]
    assert "Application Profile" in data["missing"]
    assert data["sections"]["resume"] is False


def test_readiness_endpoint_ready(client, _override_db, seeded_job):
    _activate_resume(_override_db)
    _fill_profile(_override_db)
    with Session(_override_db) as s:
        job = s.get(Job, seeded_job)
        from datetime import datetime
        job.cover_letter_generated_at = datetime.utcnow()
        s.add(job)
        s.commit()
        profile = s.exec(__import__("sqlmodel").select(ApplicationProfile)).first()
        s.add(ApplicationReference(profile_id=profile.id, name="Jane Doe"))
        s.commit()

    r = client.get(f"/api/v1/jobs/{seeded_job}/application-readiness")
    data = r.json()
    assert data["status"] == "ready"
    assert data["missing"] == []
    assert data["score"] == 100


def test_readiness_endpoint_unknown_job_404(client):
    r = client.get("/api/v1/jobs/99999/application-readiness")
    assert r.status_code == 404


# ── GET /jobs/readiness-summary ──────────────────────────────────────────────

def test_readiness_summary_covers_all_active_jobs(client, _override_db, seeded_job):
    with Session(_override_db) as s:
        s.add(make_job(external_id="test-002", url="https://seek.co.nz/job/2"))
        s.commit()

    r = client.get("/api/v1/jobs/readiness-summary")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[str(seeded_job)] == "not_ready"


def test_readiness_summary_excludes_inactive_jobs(client, _override_db, seeded_job):
    with Session(_override_db) as s:
        s.add(make_job(external_id="test-inactive", url="https://seek.co.nz/job/x", is_active=False))
        s.commit()

    r = client.get("/api/v1/jobs/readiness-summary")
    assert len(r.json()) == 1


# ── GET /jobs/{id}/application-kit ──────────────────────────────────────────

def test_application_kit_with_no_application_yet(client, seeded_job):
    r = client.get(f"/api/v1/jobs/{seeded_job}/application-kit")
    assert r.status_code == 200
    data = r.json()
    assert data["application"] is None
    assert data["active_session"] is None
    assert data["readiness"]["status"] == "not_ready"


def test_application_kit_unknown_job_404(client):
    r = client.get("/api/v1/jobs/99999/application-kit")
    assert r.status_code == 404


# ── POST /jobs/{id}/launch-application ──────────────────────────────────────

def test_launch_creates_application_and_session(client, seeded_job):
    r = client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    assert r.status_code == 200
    data = r.json()
    assert data["url"] == "https://seek.co.nz/job/1"
    assert data["application"]["job_id"] == seeded_job
    assert data["session"]["status"] == "started"
    assert data["session"]["duration_seconds"] >= 0


def test_launch_is_idempotent_reuses_active_session(client, seeded_job):
    first = client.post(f"/api/v1/jobs/{seeded_job}/launch-application").json()
    second = client.post(f"/api/v1/jobs/{seeded_job}/launch-application").json()
    assert first["session"]["id"] == second["session"]["id"]
    assert first["application"]["id"] == second["application"]["id"]


def test_launch_reuses_existing_application_if_saved(client, _override_db, seeded_job):
    with Session(_override_db) as s:
        from backend.database.models import Application
        app = Application(job_id=seeded_job)
        s.add(app)
        s.commit()
        s.refresh(app)
        app_id = app.id

    r = client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    assert r.json()["application"]["id"] == app_id


def test_launch_snapshots_versions(client, _override_db, seeded_job):
    _activate_resume(_override_db)
    _fill_profile(_override_db)

    r = client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    data = r.json()
    assert data["session"]["resume_version"] == "My Resume.pdf"
    assert data["session"]["profile_version"] is not None


def test_launch_unknown_job_404(client):
    r = client.post("/api/v1/jobs/99999/launch-application")
    assert r.status_code == 404


def test_launch_logs_started_event(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    app_id = client.get(f"/api/v1/jobs/{seeded_job}/application-kit").json()["application"]["id"]
    events = client.get(f"/api/v1/applications/{app_id}/timeline").json()
    assert any(e["event_type"] == "session_started" for e in events)


def test_relaunch_logs_resumed_event(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    app_id = client.get(f"/api/v1/jobs/{seeded_job}/application-kit").json()["application"]["id"]
    events = client.get(f"/api/v1/applications/{app_id}/timeline").json()
    assert any(e["event_type"] == "session_resumed" for e in events)


# ── POST /jobs/{id}/application-session/complete ────────────────────────────

def test_complete_applied_marks_application_applied(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    r = client.post(
        f"/api/v1/jobs/{seeded_job}/application-session/complete", json={"outcome": "applied"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["application"]["status"] == "applied"
    assert data["session"]["status"] == "completed"
    assert data["application"]["applied_at"] is not None


def test_complete_cancelled_does_not_change_application_status(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    r = client.post(
        f"/api/v1/jobs/{seeded_job}/application-session/complete", json={"outcome": "cancelled"}
    )
    data = r.json()
    assert data["application"]["status"] == "saved"
    assert data["session"]["status"] == "cancelled"


def test_complete_not_yet_leaves_session_active(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    r = client.post(
        f"/api/v1/jobs/{seeded_job}/application-session/complete", json={"outcome": "not_yet"}
    )
    data = r.json()
    assert data["session"]["status"] == "started"
    kit = client.get(f"/api/v1/jobs/{seeded_job}/application-kit").json()
    assert kit["active_session"] is not None


def test_complete_invalid_outcome_422(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    r = client.post(
        f"/api/v1/jobs/{seeded_job}/application-session/complete", json={"outcome": "maybe"}
    )
    assert r.status_code == 422


def test_complete_without_launch_returns_409(client, _override_db, seeded_job):
    with Session(_override_db) as s:
        from backend.database.models import Application
        s.add(Application(job_id=seeded_job))
        s.commit()

    r = client.post(
        f"/api/v1/jobs/{seeded_job}/application-session/complete", json={"outcome": "applied"}
    )
    assert r.status_code == 409


def test_complete_without_application_returns_404(client, seeded_job):
    r = client.post(
        f"/api/v1/jobs/{seeded_job}/application-session/complete", json={"outcome": "applied"}
    )
    assert r.status_code == 404


def test_complete_applied_logs_status_change_and_session_completed_events(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    client.post(f"/api/v1/jobs/{seeded_job}/application-session/complete", json={"outcome": "applied"})
    app_id = client.get(f"/api/v1/jobs/{seeded_job}/application-kit").json()["application"]["id"]
    events = client.get(f"/api/v1/applications/{app_id}/timeline").json()
    event_types = {e["event_type"] for e in events}
    assert "session_completed" in event_types
    assert "status_change" in event_types


def test_application_kit_active_session_cleared_after_completion(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    client.post(f"/api/v1/jobs/{seeded_job}/application-session/complete", json={"outcome": "applied"})
    kit = client.get(f"/api/v1/jobs/{seeded_job}/application-kit").json()
    assert kit["active_session"] is None


# ── Cover letter generation stamps readiness ─────────────────────────────────

def test_generating_cover_letter_prompt_stamps_readiness(client, _override_db, seeded_job):
    _activate_resume(_override_db)
    before = client.get(f"/api/v1/jobs/{seeded_job}/application-readiness").json()
    assert "Cover Letter" in before["missing"]

    r = client.get(f"/api/v1/jobs/{seeded_job}/prompts/cover_letter")
    assert r.status_code == 200

    after = client.get(f"/api/v1/jobs/{seeded_job}/application-readiness").json()
    assert "Cover Letter" not in after["missing"]


def test_generating_non_cover_letter_prompt_does_not_stamp(client, _override_db, seeded_job):
    _activate_resume(_override_db)
    r = client.get(f"/api/v1/jobs/{seeded_job}/prompts/resume_analysis")
    assert r.status_code == 200
    after = client.get(f"/api/v1/jobs/{seeded_job}/application-readiness").json()
    assert "Cover Letter" in after["missing"]
