"""Tests for the Prompt Engine (backend/prompt_engine/) — template rendering,
the config-driven action registry, and the job-scoped prompt/changes API
endpoints.

The Prompt Engine never calls an AI provider — these tests only verify plain
text generation and variable substitution, per docs/ROADMAP.md Phase 7.4.
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _sa_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from backend.database.models import Job, JobChange, Resume
from backend.prompt_engine import ACTIONS, TemplateNotFoundError, get_action, render_template
from backend.prompt_engine.engine import TEMPLATES_DIR
from backend.prompt_engine.registry import ACTIONS_CONFIG_FILE


# ── engine.render_template ──────────────────────────────────────────────────

def test_render_template_substitutes_provided_variables():
    result = render_template("cover_letter.md", {
        "job_title": "Packhouse Worker",
        "company_name": "Test Co",
        "job_location": "Auckland",
        "employment_type": "Full-time",
        "job_description": "Pack fruit.",
        "resume_name": "resume.pdf",
    })
    assert "Packhouse Worker" in result
    assert "Test Co" in result
    assert "Auckland" in result
    assert "Pack fruit." in result
    assert "resume.pdf" in result
    assert "{{" not in result


def test_render_template_missing_variable_shows_placeholder_marker():
    result = render_template("cover_letter.md", {"job_title": "Packhouse Worker"})
    assert "[company_name not provided]" in result
    assert "Packhouse Worker" in result


def test_render_template_unknown_file_raises():
    with pytest.raises(TemplateNotFoundError):
        render_template("does_not_exist.md", {})


def test_all_registered_templates_exist_on_disk():
    for action in ACTIONS:
        assert (TEMPLATES_DIR / action.template_file).exists(), action.template_file


# ── registry: config-driven loading ─────────────────────────────────────────

def test_actions_are_loaded_from_config_file_not_hardcoded():
    """The registry has no Python-level list of actions — it's a pure
    reflection of actions.json. Adding an action should only ever require
    editing that file, never this module."""
    raw = json.loads(ACTIONS_CONFIG_FILE.read_text(encoding="utf-8"))
    assert [a.id for a in ACTIONS] == [entry["id"] for entry in raw]
    assert len(ACTIONS) == len(raw)


def test_action_config_entries_have_required_fields():
    raw = json.loads(ACTIONS_CONFIG_FILE.read_text(encoding="utf-8"))
    for entry in raw:
        assert {"id", "label", "description", "template_file"} <= entry.keys()


# ── registry.get_action ─────────────────────────────────────────────────────

def test_get_action_known_id_returns_action():
    action = get_action("cover_letter")
    assert action is not None
    assert action.template_file == "cover_letter.md"


def test_get_action_unknown_id_returns_none():
    assert get_action("does_not_exist") is None


def test_registry_ids_are_unique():
    ids = [a.id for a in ACTIONS]
    assert len(ids) == len(set(ids))


# ── API: GET /prompts/actions ───────────────────────────────────────────────

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
        job = Job(
            external_id="test-001",
            source="seek",
            title="Packhouse Worker",
            employer="Test Co",
            location="Auckland",
            description="Pack fruit at a busy packhouse.",
            url="https://seek.co.nz/job/1",
        )
        s.add(job)
        s.commit()
        s.refresh(job)
        return job.id


def test_list_prompt_actions(client):
    r = client.get("/api/v1/prompts/actions")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == len(ACTIONS)
    assert {a["id"] for a in data} == {a.id for a in ACTIONS}
    assert all({"id", "label", "description", "icon"} <= a.keys() for a in data)


# ── API: GET /jobs/{job_id}/prompts/{action_id} ─────────────────────────────

def test_generate_job_prompt_without_active_resume(client, seeded_job):
    r = client.get(f"/api/v1/jobs/{seeded_job}/prompts/cover_letter")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Cover Letter"
    assert "Packhouse Worker" in data["content"]
    assert "Test Co" in data["content"]
    assert "Auckland" in data["content"]
    assert "Pack fruit at a busy packhouse." in data["content"]
    assert "No active resume" in data["content"]


def test_generate_job_prompt_with_active_resume(client, _override_db, seeded_job):
    with Session(_override_db) as s:
        resume = Resume(
            original_filename="cv.pdf",
            stored_filename="uuid-cv.pdf",
            filename="My Resume.pdf",
            file_type="pdf",
            file_size=1234,
            is_active=True,
        )
        s.add(resume)
        s.commit()

    r = client.get(f"/api/v1/jobs/{seeded_job}/prompts/cover_letter")
    assert r.status_code == 200
    assert "My Resume.pdf" in r.json()["content"]


def test_generate_job_prompt_unknown_action_404(client, seeded_job):
    r = client.get(f"/api/v1/jobs/{seeded_job}/prompts/does_not_exist")
    assert r.status_code == 404


def test_generate_job_prompt_unknown_job_404(client):
    r = client.get("/api/v1/jobs/99999/prompts/cover_letter")
    assert r.status_code == 404


def test_generate_job_prompt_missing_description_falls_back(client, _override_db):
    with Session(_override_db) as s:
        job = Job(
            external_id="test-002",
            source="seek",
            title="Fruit Picker",
            employer="Orchard Co",
            location="Nelson",
            url="https://seek.co.nz/job/2",
        )
        s.add(job)
        s.commit()
        s.refresh(job)
        job_id = job.id

    r = client.get(f"/api/v1/jobs/{job_id}/prompts/interview")
    assert r.status_code == 200
    assert "No description available." in r.json()["content"]


# ── API: GET /jobs/{job_id}/changes ─────────────────────────────────────────

def test_job_changes_empty(client, seeded_job):
    r = client.get(f"/api/v1/jobs/{seeded_job}/changes")
    assert r.status_code == 200
    assert r.json() == []


def test_job_changes_returns_history_newest_first(client, _override_db, seeded_job):
    with Session(_override_db) as s:
        s.add(JobChange(job_id=seeded_job, field_changed="salary_text", old_value="$25/hr", new_value="$27/hr"))
        s.commit()
        s.add(JobChange(job_id=seeded_job, field_changed="title", old_value="Picker", new_value="Packhouse Worker"))
        s.commit()

    r = client.get(f"/api/v1/jobs/{seeded_job}/changes")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["field_changed"] == "title"
    assert data[1]["field_changed"] == "salary_text"


def test_job_changes_unknown_job_404(client):
    r = client.get("/api/v1/jobs/99999/changes")
    assert r.status_code == 404
