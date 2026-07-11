"""Tests for AI Readiness (backend/core/ai_readiness.py) — the readiness
evaluator itself, the GET /jobs/{id}/ai-readiness endpoint, the Prompt Guard
inside GET /jobs/{id}/prompts/{action_id}, and the PATCH /jobs/{id} "Edit
Job" fast path. See docs/ROADMAP.md Phase 7.5.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _sa_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from backend.core.ai_readiness import ReadinessStatus, evaluate_ai_readiness
from backend.database.models import Job, JobChange, Resume


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


# ── evaluate_ai_readiness ────────────────────────────────────────────────────

def test_ready_when_everything_present():
    result = evaluate_ai_readiness(make_job(), make_resume())
    assert result.status == ReadinessStatus.READY
    assert result.missing == []


def test_partial_when_only_description_missing():
    result = evaluate_ai_readiness(make_job(description=None), make_resume())
    assert result.status == ReadinessStatus.PARTIAL
    assert result.missing == ["Job Description"]


def test_not_ready_when_title_missing():
    result = evaluate_ai_readiness(make_job(title=""), make_resume())
    assert result.status == ReadinessStatus.NOT_READY
    assert "Job Title" in result.missing


def test_not_ready_when_employer_missing():
    result = evaluate_ai_readiness(make_job(employer=""), make_resume())
    assert result.status == ReadinessStatus.NOT_READY
    assert "Company" in result.missing


def test_not_ready_when_no_active_resume():
    result = evaluate_ai_readiness(make_job(), None)
    assert result.status == ReadinessStatus.NOT_READY
    assert "Active Resume" in result.missing


def test_not_ready_takes_priority_over_partial():
    result = evaluate_ai_readiness(make_job(title="", description=None), make_resume())
    assert result.status == ReadinessStatus.NOT_READY
    assert "Job Description" not in result.missing


def test_not_ready_reports_all_missing_hard_fields():
    result = evaluate_ai_readiness(make_job(title="", employer=""), None)
    assert result.status == ReadinessStatus.NOT_READY
    assert set(result.missing) == {"Job Title", "Company", "Active Resume"}


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


# ── GET /jobs/{id}/ai-readiness ─────────────────────────────────────────────

def test_ai_readiness_endpoint_not_ready_without_resume(client, seeded_job):
    r = client.get(f"/api/v1/jobs/{seeded_job}/ai-readiness")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "not_ready"
    assert "Active Resume" in data["missing"]


def test_ai_readiness_endpoint_ready(client, _override_db, seeded_job):
    _activate_resume(_override_db)
    r = client.get(f"/api/v1/jobs/{seeded_job}/ai-readiness")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ready"
    assert data["missing"] == []


def test_ai_readiness_endpoint_partial(client, _override_db):
    with Session(_override_db) as s:
        job = make_job(description=None)
        s.add(job)
        s.commit()
        s.refresh(job)
        job_id = job.id
    _activate_resume(_override_db)

    r = client.get(f"/api/v1/jobs/{job_id}/ai-readiness")
    data = r.json()
    assert data["status"] == "partial"
    assert data["missing"] == ["Job Description"]


def test_ai_readiness_endpoint_unknown_job_404(client):
    r = client.get("/api/v1/jobs/99999/ai-readiness")
    assert r.status_code == 404


# ── Prompt Guard ─────────────────────────────────────────────────────────────

def test_prompt_guard_blocks_generation_when_not_ready(client, seeded_job):
    r = client.get(f"/api/v1/jobs/{seeded_job}/prompts/cover_letter")
    assert r.status_code == 409
    assert "Active Resume" in r.json()["message"]


def test_prompt_guard_allows_generation_when_ready(client, _override_db, seeded_job):
    _activate_resume(_override_db)
    r = client.get(f"/api/v1/jobs/{seeded_job}/prompts/cover_letter")
    assert r.status_code == 200
    data = r.json()
    assert data["readiness_status"] == "ready"
    assert data["disclaimer"] is None


def test_prompt_guard_adds_disclaimer_when_partial(client, _override_db):
    with Session(_override_db) as s:
        job = make_job(description=None)
        s.add(job)
        s.commit()
        s.refresh(job)
        job_id = job.id
    _activate_resume(_override_db)

    r = client.get(f"/api/v1/jobs/{job_id}/prompts/cover_letter")
    assert r.status_code == 200
    data = r.json()
    assert data["readiness_status"] == "partial"
    assert data["disclaimer"] is not None
    assert "missing" in data["disclaimer"].lower()
    # The guardrail instruction must be baked into the copyable prompt text
    # itself so Claude doesn't invent a job description.
    assert "do not invent or assume" in data["content"].lower()


# ── PATCH /jobs/{id} — Edit Job ──────────────────────────────────────────────

def test_patch_job_updates_fields(client, seeded_job):
    r = client.patch(f"/api/v1/jobs/{seeded_job}", json={"description": "New description here."})
    assert r.status_code == 200
    assert r.json()["description"] == "New description here."


def test_patch_job_logs_a_job_change(client, _override_db, seeded_job):
    client.patch(f"/api/v1/jobs/{seeded_job}", json={"title": "Updated Title"})
    with Session(_override_db) as s:
        changes = list(s.exec(select(JobChange).where(JobChange.job_id == seeded_job)).all())
    assert len(changes) == 1
    assert changes[0].field_changed == "title"
    assert changes[0].old_value == "Packhouse Worker"
    assert changes[0].new_value == "Updated Title"


def test_patch_job_no_change_logged_when_value_unchanged(client, _override_db, seeded_job):
    client.patch(f"/api/v1/jobs/{seeded_job}", json={"title": "Packhouse Worker"})
    with Session(_override_db) as s:
        changes = list(s.exec(select(JobChange).where(JobChange.job_id == seeded_job)).all())
    assert len(changes) == 0


def test_patch_job_fixing_missing_description_moves_to_ready(client, _override_db):
    with Session(_override_db) as s:
        job = make_job(description=None)
        s.add(job)
        s.commit()
        s.refresh(job)
        job_id = job.id
    _activate_resume(_override_db)

    assert client.get(f"/api/v1/jobs/{job_id}/ai-readiness").json()["status"] == "partial"
    client.patch(f"/api/v1/jobs/{job_id}", json={"description": "Now has a description."})
    assert client.get(f"/api/v1/jobs/{job_id}/ai-readiness").json()["status"] == "ready"


def test_patch_job_unknown_job_404(client):
    r = client.patch("/api/v1/jobs/99999", json={"title": "X"})
    assert r.status_code == 404
