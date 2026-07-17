"""Tests for Application Flow Reliability — the Application Kit's
listing-url-exactness signal (backend/core/listing_url.py) and the
"Listing Unavailable" outcome on manual completion. See docs/ROADMAP.md
"Application Flow Reliability & Assisted Autofill" milestone.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _sa_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from backend.database.models import Job


def make_job(**overrides) -> Job:
    defaults = dict(
        external_id="test-001",
        source="trademe",
        title="Farm Worker - Fixed Term",
        employer="Test Co",
        location="Dunedin, Otago",
        url="https://www.trademe.co.nz/a/jobs/agriculture-fishing-forestry/farming/otago/dunedin/full-time/listing/6016040732",
    )
    defaults.update(overrides)
    return Job(**defaults)


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


# ── GET /jobs/{id}/application-kit — listing_url_exact ──────────────────────

def test_application_kit_reports_exact_url(client, seeded_job):
    r = client.get(f"/api/v1/jobs/{seeded_job}/application-kit")
    assert r.status_code == 200
    data = r.json()
    assert data["listing_url_exact"] is True
    assert data["fallback_link"] is None


def test_application_kit_reports_category_url_as_not_exact(client, _override_db):
    with Session(_override_db) as s:
        job = make_job(
            external_id="test-002",
            url="https://www.trademe.co.nz/a/jobs/agriculture-fishing-forestry/farming/otago/dunedin",
        )
        s.add(job)
        s.commit()
        s.refresh(job)
        job_id = job.id

    r = client.get(f"/api/v1/jobs/{job_id}/application-kit")
    data = r.json()
    assert data["listing_url_exact"] is False
    assert data["fallback_link"] is not None
    assert data["fallback_is_search"] is True
    assert "trademe.co.nz" in data["fallback_link"]


def test_application_kit_fallback_for_browse_only_source(client, _override_db):
    with Session(_override_db) as s:
        job = make_job(
            external_id="test-003", source="picknz", url="https://jobs.picknz.co.nz/",
        )
        s.add(job)
        s.commit()
        s.refresh(job)
        job_id = job.id

    r = client.get(f"/api/v1/jobs/{job_id}/application-kit")
    data = r.json()
    assert data["listing_url_exact"] is False
    assert data["fallback_link"] == "https://jobs.picknz.co.nz/"
    assert data["fallback_is_search"] is False


def test_application_kit_unknown_job_404(client):
    r = client.get("/api/v1/jobs/99999/application-kit")
    assert r.status_code == 404


# ── POST .../application-session/complete — listing_unavailable outcome ────

def test_listing_unavailable_sets_application_status(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    r = client.post(
        f"/api/v1/jobs/{seeded_job}/application-session/complete",
        json={"outcome": "listing_unavailable"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["application"]["status"] == "unavailable"
    assert data["session"]["status"] == "cancelled"


def test_listing_unavailable_is_not_rejected_or_cancelled_status(client, seeded_job):
    """Distinct from both REJECTED (employer decision) and the plain
    'cancelled' session outcome (user's own choice not to apply)."""
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    r = client.post(
        f"/api/v1/jobs/{seeded_job}/application-session/complete",
        json={"outcome": "listing_unavailable"},
    )
    status = r.json()["application"]["status"]
    assert status not in ("rejected", "cancelled", "saved", "applied")


def test_listing_unavailable_logs_timeline_event(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    app_id = client.get(f"/api/v1/jobs/{seeded_job}/application-kit").json()["application"]["id"]
    client.post(
        f"/api/v1/jobs/{seeded_job}/application-session/complete",
        json={"outcome": "listing_unavailable"},
    )
    events = client.get(f"/api/v1/applications/{app_id}/timeline").json()
    event_types = [e["event_type"] for e in events]
    assert "session_listing_unavailable" in event_types


def test_listing_unavailable_preserves_application_for_history(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    client.post(
        f"/api/v1/jobs/{seeded_job}/application-session/complete",
        json={"outcome": "listing_unavailable"},
    )
    # Still visible in the tracker — not deleted.
    r = client.get("/api/v1/applications/", params={"status": "unavailable"})
    assert len(r.json()) == 1


def test_listing_unavailable_clears_active_session(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    client.post(
        f"/api/v1/jobs/{seeded_job}/application-session/complete",
        json={"outcome": "listing_unavailable"},
    )
    kit = client.get(f"/api/v1/jobs/{seeded_job}/application-kit").json()
    assert kit["active_session"] is None


def test_invalid_outcome_still_rejected(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    r = client.post(
        f"/api/v1/jobs/{seeded_job}/application-session/complete",
        json={"outcome": "not_a_real_outcome"},
    )
    assert r.status_code == 422


# ── GET /applications/pipeline — unavailable count ──────────────────────────

def test_pipeline_counts_unavailable_applications(client, seeded_job):
    client.post(f"/api/v1/jobs/{seeded_job}/launch-application")
    client.post(
        f"/api/v1/jobs/{seeded_job}/application-session/complete",
        json={"outcome": "listing_unavailable"},
    )
    r = client.get("/api/v1/applications/pipeline")
    data = r.json()
    assert data["unavailable"] == 1
    assert data["total"] == 1
