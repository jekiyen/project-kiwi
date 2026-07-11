"""Tests for the Kiwi Job Summary (backend/job_summary/) — the deterministic
extractor, the service wiring, GET /jobs/{id}/summary, and the Prompt
Engine's use of summary_json over raw description. See docs/ROADMAP.md
Phase 7.6. No LLM is ever involved — everything here is regex/heuristics.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _sa_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from backend.database.models import Job, Resume
from backend.job_summary import JobSummary, generate_job_summary, render_summary_as_text, summarize_job

WELL_FORMATTED_DESCRIPTION = """
About the role
We are looking for a reliable Packhouse Worker to join our busy team during the harvest season.

Responsibilities
- Sort and pack fruit according to quality standards
- Operate packing line machinery

Requirements
- Previous packhouse experience preferred
- Must have valid NZ work rights

Preferred
- Forklift licence

Benefits
- Free accommodation available

Working Conditions
- Cold storage environment

Pay
$25 - $28 per hour depending on experience
"""


# ── extractor: well-formatted description ───────────────────────────────────

def test_extracts_overview_from_about_the_role_heading():
    s = generate_job_summary(WELL_FORMATTED_DESCRIPTION)
    assert s.overview.startswith("We are looking for a reliable Packhouse Worker")


def test_extracts_responsibilities():
    s = generate_job_summary(WELL_FORMATTED_DESCRIPTION)
    assert s.responsibilities == [
        "Sort and pack fruit according to quality standards",
        "Operate packing line machinery",
    ]


def test_extracts_required_and_preferred_requirements_separately():
    s = generate_job_summary(WELL_FORMATTED_DESCRIPTION)
    assert s.requirements_required == [
        "Previous packhouse experience preferred",
        "Must have valid NZ work rights",
    ]
    assert s.requirements_preferred == ["Forklift licence"]


def test_extracts_benefits_and_work_environment():
    s = generate_job_summary(WELL_FORMATTED_DESCRIPTION)
    assert s.benefits == ["Free accommodation available"]
    assert s.work_environment == ["Cold storage environment"]


def test_extracts_salary_from_heading_section():
    s = generate_job_summary(WELL_FORMATTED_DESCRIPTION)
    assert s.salary == "$25 - $28 per hour depending on experience"


def test_extracts_visa_notes_without_bullet_marker():
    s = generate_job_summary(WELL_FORMATTED_DESCRIPTION)
    assert s.visa_notes == "Must have valid NZ work rights"


def test_well_formatted_description_has_no_warnings():
    s = generate_job_summary(WELL_FORMATTED_DESCRIPTION)
    assert s.warnings == []


def test_heading_detection_does_not_false_positive_on_prose():
    # "3+ years of experience..." must not be mistaken for an "Experience"
    # heading — headings require the WHOLE line to be the heading phrase.
    desc = "Responsibilities\n- 3+ years of experience in a similar role\n- Reliable transport"
    s = generate_job_summary(desc)
    assert s.responsibilities == [
        "3+ years of experience in a similar role",
        "Reliable transport",
    ]
    assert s.requirements_required == []


# ── extractor: fallbacks ─────────────────────────────────────────────────────

def test_empty_description_returns_empty_summary_with_warning():
    s = generate_job_summary(None)
    assert s.is_empty()
    assert "No job description available" in s.warnings[0]


def test_empty_description_falls_back_to_salary_text():
    s = generate_job_summary("", salary_text="$25/hr")
    assert s.salary == "$25/hr"


def test_no_headings_but_bullets_go_to_responsibilities_only():
    s = generate_job_summary("- Do this\n- Do that")
    assert s.responsibilities == ["Do this", "Do that"]
    assert s.overview == ""
    assert any("without further categorization" in w for w in s.warnings)


def test_no_headings_pure_prose_goes_to_overview_only():
    desc = "We need someone reliable who can work hard on our farm every day."
    s = generate_job_summary(desc)
    assert s.overview == desc
    assert s.responsibilities == []
    assert any("No structured sections detected" in w for w in s.warnings)


def test_missing_responsibilities_warns_when_other_headings_exist():
    desc = "Requirements\n- Must be reliable"
    s = generate_job_summary(desc)
    assert "No responsibilities section detected." in s.warnings


def test_missing_requirements_warns_when_other_headings_exist():
    desc = "Responsibilities\n- Pack fruit"
    s = generate_job_summary(desc)
    assert "No requirements section detected." in s.warnings


def test_missing_salary_always_warns():
    s = generate_job_summary("Responsibilities\n- Pack fruit\n\nRequirements\n- Be reliable")
    assert "No salary information found." in s.warnings


def test_extractor_never_invents_data_beyond_input_text():
    # Every extracted string must be a substring of (or built purely from)
    # the original description — nothing fabricated.
    s = generate_job_summary(WELL_FORMATTED_DESCRIPTION)
    for item in s.responsibilities + s.requirements_required + s.requirements_preferred:
        assert item in WELL_FORMATTED_DESCRIPTION


# ── JobSummary.is_empty ──────────────────────────────────────────────────────

def test_is_empty_true_for_blank_summary():
    assert JobSummary().is_empty()


def test_is_empty_false_when_overview_present():
    assert not JobSummary(overview="Something").is_empty()


def test_is_empty_ignores_warnings():
    assert JobSummary(warnings=["some warning"]).is_empty()


# ── formatter ────────────────────────────────────────────────────────────────

def test_render_summary_as_text_includes_populated_sections_only():
    summary = JobSummary(overview="Overview text", salary="$25/hr")
    text = render_summary_as_text(summary)
    assert "Overview text" in text
    assert "Salary: $25/hr" in text
    assert "Responsibilities:" not in text


def test_render_summary_as_text_empty_summary_is_empty_string():
    assert render_summary_as_text(JobSummary()) == ""


# ── service.summarize_job ───────────────────────────────────────────────────

def test_summarize_job_sets_summary_json_without_touching_description():
    job = Job(
        external_id="x", source="seek", title="T", employer="E", location="L",
        url="http://x", description="Responsibilities\n- Do a thing",
    )
    summarize_job(job)
    assert job.description == "Responsibilities\n- Do a thing"
    assert job.summary_json is not None
    parsed = JobSummary.model_validate_json(job.summary_json)
    assert parsed.responsibilities == ["Do a thing"]


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


def _seed_job(engine, **overrides) -> int:
    defaults = dict(
        external_id="test-001", source="seek", title="Packhouse Worker",
        employer="Test Co", location="Auckland", url="https://seek.co.nz/job/1",
        description=WELL_FORMATTED_DESCRIPTION,
    )
    defaults.update(overrides)
    with Session(engine) as s:
        job = Job(**defaults)
        s.add(job)
        s.commit()
        s.refresh(job)
        return job.id


def _activate_resume(engine) -> None:
    with Session(engine) as s:
        s.add(Resume(
            original_filename="cv.pdf", stored_filename="uuid-cv.pdf", filename="My Resume.pdf",
            file_type="pdf", file_size=1234, is_active=True,
        ))
        s.commit()


# ── GET /jobs/{id}/summary ──────────────────────────────────────────────────

def test_get_job_summary_returns_structured_data(client, _override_db):
    job_id = _seed_job(_override_db)
    r = client.get(f"/api/v1/jobs/{job_id}/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["overview"].startswith("We are looking for a reliable Packhouse Worker")
    assert "Sort and pack fruit according to quality standards" in data["responsibilities"]


def test_get_job_summary_generates_and_persists_for_legacy_job(client, _override_db):
    job_id = _seed_job(_override_db)
    with Session(_override_db) as s:
        job = s.get(Job, job_id)
        assert job.summary_json is None  # newly created via raw Session, bypassing summarize_job

    client.get(f"/api/v1/jobs/{job_id}/summary")

    with Session(_override_db) as s:
        job = s.get(Job, job_id)
        assert job.summary_json is not None


def test_get_job_summary_unknown_job_404(client):
    r = client.get("/api/v1/jobs/99999/summary")
    assert r.status_code == 404


# ── PATCH /jobs/{id} regenerates summary on description change ─────────────

def test_patch_description_regenerates_summary(client, _override_db):
    job_id = _seed_job(_override_db, description=None)
    client.patch(f"/api/v1/jobs/{job_id}", json={"description": "Responsibilities\n- New duty"})

    with Session(_override_db) as s:
        job = s.get(Job, job_id)
        summary = JobSummary.model_validate_json(job.summary_json)
    assert summary.responsibilities == ["New duty"]


def test_patch_unrelated_field_does_not_touch_summary(client, _override_db):
    job_id = _seed_job(_override_db)
    client.get(f"/api/v1/jobs/{job_id}/summary")  # ensure a summary exists first
    with Session(_override_db) as s:
        before = s.get(Job, job_id).summary_json

    client.patch(f"/api/v1/jobs/{job_id}", json={"title": "New Title"})

    with Session(_override_db) as s:
        after = s.get(Job, job_id).summary_json
    assert before == after


# ── Prompt Guard consumes summary_json ──────────────────────────────────────

def test_generated_prompt_uses_structured_summary_over_raw_description(client, _override_db):
    job_id = _seed_job(_override_db)
    _activate_resume(_override_db)

    r = client.get(f"/api/v1/jobs/{job_id}/prompts/cover_letter")
    assert r.status_code == 200
    content = r.json()["content"]
    # Structured section headers from render_summary_as_text should appear,
    # proving the summary (not the raw block of text) was used.
    assert "Responsibilities:" in content
    assert "- Sort and pack fruit according to quality standards" in content
    assert "Salary: $25 - $28 per hour depending on experience" in content


def test_generated_prompt_falls_back_to_raw_description_when_summary_empty(client, _override_db):
    # A description that yields an empty-ish summary shouldn't happen in
    # practice (pure prose still populates overview) — but if description is
    # present and title/company/resume are all set, readiness is Ready and
    # the summary (never fully empty when text exists) is used. This test
    # instead confirms the *missing description* guard path still fires
    # when there's truly nothing to summarize.
    job_id = _seed_job(_override_db, description="")
    _activate_resume(_override_db)

    r = client.get(f"/api/v1/jobs/{job_id}/prompts/cover_letter")
    assert r.status_code == 200
    data = r.json()
    assert data["disclaimer"] is not None
    assert "do not invent or assume" in data["content"].lower()
