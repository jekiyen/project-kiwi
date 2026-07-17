"""Tests for Job Intelligence (backend/core/job_intelligence.py) — the
deterministic scoring/recommendation/gap-analysis service, and the endpoints
that consume it (GET /jobs/{id}/job-intelligence, GET /jobs/job-intelligence-
summary, GET /jobs/{id}/similar, and the new "good_fit" Prompt Engine
action). See docs/ROADMAP.md Phase 9.
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _sa_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from backend.core.job_intelligence import (
    RecommendationLevel,
    evaluate_job_intelligence,
    find_similar_jobs,
    recommendation_for_score,
)
from backend.database.models import Job, Resume, RolePriority
from backend.job_summary import JobSummary


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


EMPTY_SUMMARY = JobSummary()
FILLED_SUMMARY = JobSummary(requirements_required=["Must lift 20kg", "Own steel-cap boots"])


# ── recommendation_for_score ─────────────────────────────────────────────────

@pytest.mark.parametrize("score,expected", [
    (100, RecommendationLevel.HIGHLY_RECOMMENDED),
    (80, RecommendationLevel.HIGHLY_RECOMMENDED),
    (79, RecommendationLevel.RECOMMENDED),
    (60, RecommendationLevel.RECOMMENDED),
    (59, RecommendationLevel.CONSIDER),
    (35, RecommendationLevel.CONSIDER),
    (34, RecommendationLevel.LOW_PRIORITY),
    (0, RecommendationLevel.LOW_PRIORITY),
])
def test_recommendation_thresholds(score, expected):
    assert recommendation_for_score(score) == expected


# ── evaluate_job_intelligence — scoring ──────────────────────────────────────

def test_uses_existing_ai_match_score_when_present():
    job = make_job(ai_match_score=85.0, ai_confidence=80)
    result = evaluate_job_intelligence(job, EMPTY_SUMMARY)
    assert result.score == 85
    assert result.confidence == 80
    assert result.recommendation == RecommendationLevel.HIGHLY_RECOMMENDED


def test_falls_back_to_matcher_when_unscored():
    job = make_job(role_priority=RolePriority.P1, ai_match_score=None)
    result = evaluate_job_intelligence(job, EMPTY_SUMMARY)
    assert result.score == 80  # matcher's P1 base (0.8) * 100
    assert result.confidence < 80  # lower confidence than an actually-analysed job


def test_unscored_job_without_role_priority_gets_low_fallback_score():
    job = make_job(role_priority=None, ai_match_score=None)
    result = evaluate_job_intelligence(job, EMPTY_SUMMARY)
    assert result.score == 30  # matcher's default (0.3) * 100


def test_deterministic_repeated_calls_give_same_result():
    job = make_job(ai_match_score=62.0, ai_confidence=75)
    r1 = evaluate_job_intelligence(job, EMPTY_SUMMARY)
    r2 = evaluate_job_intelligence(job, EMPTY_SUMMARY)
    assert r1 == r2


# ── evaluate_job_intelligence — reasons ──────────────────────────────────────

def test_reasons_prefer_stored_ai_reasons():
    job = make_job(ai_match_score=70.0, ai_reasons=json.dumps(["Custom reason A", "Custom reason B"]))
    result = evaluate_job_intelligence(job, EMPTY_SUMMARY)
    assert result.reasons == ["Custom reason A", "Custom reason B"]


def test_reasons_fall_back_when_ai_reasons_missing():
    job = make_job(ai_match_score=None, role_priority=RolePriority.P1, visa_accredited_employer=True)
    result = evaluate_job_intelligence(job, EMPTY_SUMMARY)
    assert any("P1" in r for r in result.reasons)
    assert any("accredited" in r.lower() for r in result.reasons)


def test_reasons_fall_back_on_malformed_ai_reasons_json():
    job = make_job(ai_match_score=70.0, ai_reasons="not valid json")
    result = evaluate_job_intelligence(job, EMPTY_SUMMARY)
    assert len(result.reasons) > 0  # doesn't raise, produces a sane fallback


# ── evaluate_job_intelligence — missing requirements ─────────────────────────

def test_missing_requirements_flags_absent_fields():
    job = make_job(salary_text=None, description=None)
    result = evaluate_job_intelligence(job, EMPTY_SUMMARY)
    assert "Salary: Not specified" in result.missing_requirements
    assert "Job Description: Not specified" in result.missing_requirements
    assert "Employment Type: Not specified" in result.missing_requirements
    assert "Requirements: Not specified" in result.missing_requirements
    assert "Visa / Work Rights Policy: Not specified" in result.missing_requirements


def test_missing_requirements_excludes_present_fields():
    job = make_job(salary_text="$25/hr", description="Full description here.", visa_accredited_employer=True)
    result = evaluate_job_intelligence(job, FILLED_SUMMARY)
    assert "Salary: Not specified" not in result.missing_requirements
    assert "Job Description: Not specified" not in result.missing_requirements
    assert "Requirements: Not specified" not in result.missing_requirements
    assert "Visa / Work Rights Policy: Not specified" not in result.missing_requirements
    # No job source has this field at all — always flagged, never invented.
    assert "Employment Type: Not specified" in result.missing_requirements


def test_missing_requirements_never_invents_a_value():
    """Every entry must literally end with 'Not specified' — nothing guessed."""
    job = make_job(salary_text=None, description=None)
    result = evaluate_job_intelligence(job, EMPTY_SUMMARY)
    assert all(item.endswith("Not specified") for item in result.missing_requirements)


# ── find_similar_jobs ─────────────────────────────────────────────────────────

def test_similar_jobs_matches_on_role_priority_and_location():
    job = make_job(id=1, role_priority=RolePriority.P1, location="Auckland", title="Packhouse Worker")
    candidates = [
        make_job(id=2, external_id="c2", url="u2", role_priority=RolePriority.P1, location="Auckland", title="Orchard Hand"),
        make_job(id=3, external_id="c3", url="u3", role_priority=RolePriority.P3, location="Wellington", title="General Labourer"),
    ]
    similar = find_similar_jobs(job, candidates)
    assert similar[0].job.id == 2
    assert similar[0].similarity_score > 0
    ids = [s.job.id for s in similar]
    assert 3 not in ids or similar[-1].job.id == 3


def test_similar_jobs_excludes_itself():
    job = make_job(id=1, title="Packhouse Worker")
    candidates = [make_job(id=1, title="Packhouse Worker"), make_job(id=2, external_id="c2", url="u2", title="Different Role Entirely")]
    similar = find_similar_jobs(job, candidates)
    assert all(s.job.id != 1 for s in similar)


def test_similar_jobs_title_token_overlap():
    job = make_job(id=1, title="Warehouse Assistant", role_priority=None, location="Hamilton")
    candidates = [
        make_job(id=2, external_id="c2", url="u2", title="Warehouse Assistant Needed", role_priority=None, location="Tauranga"),
        make_job(id=3, external_id="c3", url="u3", title="Completely Unrelated Chef Role", role_priority=None, location="Dunedin"),
    ]
    similar = find_similar_jobs(job, candidates)
    ids = [s.job.id for s in similar]
    assert 2 in ids
    assert 3 not in ids


def test_similar_jobs_respects_limit():
    job = make_job(id=1, role_priority=RolePriority.P1, location="Auckland")
    candidates = [
        make_job(id=i, external_id=f"c{i}", url=f"u{i}", role_priority=RolePriority.P1, location="Auckland")
        for i in range(2, 10)
    ]
    similar = find_similar_jobs(job, candidates, limit=3)
    assert len(similar) == 3


def test_similar_jobs_empty_when_nothing_matches():
    job = make_job(id=1, role_priority=RolePriority.P1, location="Auckland", title="Packhouse Worker")
    candidates = [make_job(id=2, external_id="c2", url="u2", role_priority=RolePriority.P3, location="Dunedin", title="Zzz Totally Different")]
    similar = find_similar_jobs(job, candidates)
    assert similar == []


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


# ── GET /jobs/{id}/job-intelligence ──────────────────────────────────────────

def test_job_intelligence_endpoint_unscored_job(client, seeded_job):
    # seeded_job has no role_priority set (that's assigned during scraper
    # ingestion, not on the raw Job row) — matcher's default fallback applies.
    r = client.get(f"/api/v1/jobs/{seeded_job}/job-intelligence")
    assert r.status_code == 200
    data = r.json()
    assert data["score"] == 30
    assert data["recommendation"] == "low_priority"
    assert isinstance(data["reasons"], list) and len(data["reasons"]) > 0
    assert isinstance(data["missing_requirements"], list)


def test_job_intelligence_endpoint_unknown_job_404(client):
    r = client.get("/api/v1/jobs/99999/job-intelligence")
    assert r.status_code == 404


def test_job_intelligence_endpoint_uses_stored_ai_analysis(client, _override_db, seeded_job):
    with Session(_override_db) as s:
        job = s.get(Job, seeded_job)
        job.ai_match_score = 42.0
        job.ai_confidence = 65
        job.ai_reasons = json.dumps(["Stored reason"])
        s.add(job)
        s.commit()

    r = client.get(f"/api/v1/jobs/{seeded_job}/job-intelligence")
    data = r.json()
    assert data["score"] == 42
    assert data["confidence"] == 65
    assert data["reasons"] == ["Stored reason"]
    assert data["recommendation"] == "consider"


# ── GET /jobs/job-intelligence-summary ───────────────────────────────────────

def test_job_intelligence_summary_covers_all_active_jobs(client, _override_db, seeded_job):
    with Session(_override_db) as s:
        s.add(make_job(external_id="test-002", url="https://seek.co.nz/job/2", is_active=True))
        s.add(make_job(external_id="test-003", url="https://seek.co.nz/job/3", is_active=False))
        s.commit()

    r = client.get("/api/v1/jobs/job-intelligence-summary")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2  # inactive job excluded
    assert str(seeded_job) in data
    assert "recommendation" in data[str(seeded_job)]
    assert "score" in data[str(seeded_job)]


# ── GET /jobs/{id}/similar ───────────────────────────────────────────────────

def test_similar_jobs_endpoint(client, _override_db, seeded_job):
    with Session(_override_db) as s:
        s.add(make_job(external_id="test-002", url="https://seek.co.nz/job/2", title="Packhouse Assistant"))
        s.commit()

    r = client.get(f"/api/v1/jobs/{seeded_job}/similar")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["title"] == "Packhouse Assistant"
    assert data[0]["similarity_score"] > 0


def test_similar_jobs_endpoint_unknown_job_404(client):
    r = client.get("/api/v1/jobs/99999/similar")
    assert r.status_code == 404


def test_similar_jobs_endpoint_excludes_inactive_jobs(client, _override_db, seeded_job):
    with Session(_override_db) as s:
        s.add(make_job(
            external_id="test-002", url="https://seek.co.nz/job/2",
            title="Packhouse Assistant", is_active=False,
        ))
        s.commit()

    r = client.get(f"/api/v1/jobs/{seeded_job}/similar")
    assert r.json() == []


# ── Prompt Engine: "good_fit" action ─────────────────────────────────────────

def test_good_fit_action_is_registered(client):
    r = client.get("/api/v1/prompts/actions")
    data = r.json()
    assert any(a["id"] == "good_fit" for a in data)


def test_good_fit_prompt_includes_match_reasons(client, _override_db, seeded_job):
    _activate_resume(_override_db)
    with Session(_override_db) as s:
        job = s.get(Job, seeded_job)
        job.ai_reasons = json.dumps(["Strong alignment with P1 target roles."])
        s.add(job)
        s.commit()

    r = client.get(f"/api/v1/jobs/{seeded_job}/prompts/good_fit")
    assert r.status_code == 200
    content = r.json()["content"]
    assert "Strong alignment with P1 target roles." in content
    assert "{{" not in content


def test_good_fit_prompt_blocked_without_resume(client, seeded_job):
    r = client.get(f"/api/v1/jobs/{seeded_job}/prompts/good_fit")
    assert r.status_code == 409
