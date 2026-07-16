"""Tests for the Application Profile API — the single source of truth for
reusable applicant information. Exactly one profile ever exists; GET/PUT
upsert it, and references are fully replaced on every PUT."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _sa_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel


# ── Fixtures ──────────────────────────────────────────────────────────────────

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


_FULL_BODY = {
    "full_name": "Rizky Aditya",
    "preferred_name": "Rizky",
    "email": "rizky@example.com",
    "phone": "+62 812 0000 0000",
    "current_address": "Jl. Example No. 1",
    "city": "Jakarta",
    "country": "Indonesia",
    "nationality": "Indonesian",
    "work_rights_current_country": "Indonesia",
    "visa_status": "None",
    "eligible_to_work_nz": False,
    "need_sponsorship": True,
    "driver_license": True,
    "own_vehicle": False,
    "linkedin_url": "https://linkedin.com/in/rizky",
    "portfolio_url": "https://rizky.design",
    "github_url": "https://github.com/rizky",
    "website_url": "https://rizky.dev",
    "emergency_contact_name": "Budi Aditya",
    "emergency_contact_relationship": "Father",
    "emergency_contact_phone": "+62 811 1111 1111",
    "notes": "Prefers packhouse or orchard roles.",
    "references": [
        {"name": "Jane Doe", "company": "Acme Co", "relationship": "Manager", "email": "jane@acme.com", "phone": "111"},
        {"name": "John Roe", "company": "Beta Ltd", "relationship": "Colleague", "email": "john@beta.com", "phone": "222"},
    ],
}


# ── GET — lazy singleton creation ────────────────────────────────────────────

def test_get_creates_empty_profile_on_first_call(client):
    r = client.get("/api/v1/application-profile/")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == 1
    assert data["full_name"] is None
    assert data["references"] == []
    assert data["eligible_to_work_nz"] is False


def test_get_is_idempotent_single_row(client):
    first = client.get("/api/v1/application-profile/").json()
    second = client.get("/api/v1/application-profile/").json()
    assert first["id"] == second["id"] == 1


# ── PUT — full upsert ────────────────────────────────────────────────────────

def test_put_persists_all_personal_fields(client):
    r = client.put("/api/v1/application-profile/", json=_FULL_BODY)
    assert r.status_code == 200
    data = r.json()
    assert data["full_name"] == "Rizky Aditya"
    assert data["preferred_name"] == "Rizky"
    assert data["email"] == "rizky@example.com"
    assert data["city"] == "Jakarta"
    assert data["nationality"] == "Indonesian"


def test_put_persists_work_rights_fields(client):
    r = client.put("/api/v1/application-profile/", json=_FULL_BODY)
    data = r.json()
    assert data["work_rights_current_country"] == "Indonesia"
    assert data["need_sponsorship"] is True
    assert data["driver_license"] is True
    assert data["own_vehicle"] is False
    assert data["eligible_to_work_nz"] is False


def test_put_persists_professional_links(client):
    r = client.put("/api/v1/application-profile/", json=_FULL_BODY)
    data = r.json()
    assert data["linkedin_url"] == "https://linkedin.com/in/rizky"
    assert data["github_url"] == "https://github.com/rizky"


def test_put_persists_emergency_contact(client):
    r = client.put("/api/v1/application-profile/", json=_FULL_BODY)
    data = r.json()
    assert data["emergency_contact_name"] == "Budi Aditya"
    assert data["emergency_contact_relationship"] == "Father"


def test_put_persists_notes(client):
    r = client.put("/api/v1/application-profile/", json=_FULL_BODY)
    assert r.json()["notes"] == "Prefers packhouse or orchard roles."


def test_put_never_creates_a_second_profile_row(client):
    client.put("/api/v1/application-profile/", json=_FULL_BODY)
    client.put("/api/v1/application-profile/", json=_FULL_BODY)
    r = client.get("/api/v1/application-profile/")
    assert r.json()["id"] == 1


def test_get_reflects_last_put(client):
    client.put("/api/v1/application-profile/", json=_FULL_BODY)
    r = client.get("/api/v1/application-profile/")
    assert r.json()["full_name"] == "Rizky Aditya"


def test_put_updates_updated_at(client):
    first = client.put("/api/v1/application-profile/", json=_FULL_BODY).json()
    second_body = {**_FULL_BODY, "full_name": "Changed Name"}
    second = client.put("/api/v1/application-profile/", json=second_body).json()
    assert second["full_name"] == "Changed Name"
    assert second["updated_at"] >= first["updated_at"]


def test_put_with_partial_body_uses_defaults_for_omitted_fields(client):
    """PUT is a full replace, not a patch — omitted optional fields reset to null/false."""
    client.put("/api/v1/application-profile/", json=_FULL_BODY)
    r = client.put("/api/v1/application-profile/", json={"full_name": "Only Name"})
    data = r.json()
    assert data["full_name"] == "Only Name"
    assert data["email"] is None
    assert data["need_sponsorship"] is False
    assert data["references"] == []


# ── References — full replace on every PUT ──────────────────────────────────

def test_put_creates_references(client):
    r = client.put("/api/v1/application-profile/", json=_FULL_BODY)
    refs = r.json()["references"]
    assert len(refs) == 2
    assert refs[0]["name"] == "Jane Doe"
    assert refs[0]["company"] == "Acme Co"
    assert refs[1]["name"] == "John Roe"


def test_put_replaces_references_wholesale(client):
    client.put("/api/v1/application-profile/", json=_FULL_BODY)
    replaced = {**_FULL_BODY, "references": [
        {"name": "Only One", "company": None, "relationship": None, "email": None, "phone": None},
    ]}
    r = client.put("/api/v1/application-profile/", json=replaced)
    refs = r.json()["references"]
    assert len(refs) == 1
    assert refs[0]["name"] == "Only One"


def test_put_can_clear_all_references(client):
    client.put("/api/v1/application-profile/", json=_FULL_BODY)
    r = client.put("/api/v1/application-profile/", json={**_FULL_BODY, "references": []})
    assert r.json()["references"] == []


def test_reference_requires_name(client):
    bad = {**_FULL_BODY, "references": [{"company": "Acme"}]}
    r = client.put("/api/v1/application-profile/", json=bad)
    assert r.status_code == 422


# ── Validation ────────────────────────────────────────────────────────────────

def test_put_rejects_overlong_notes(client):
    bad = {**_FULL_BODY, "notes": "x" * 6000}
    r = client.put("/api/v1/application-profile/", json=bad)
    assert r.status_code == 422


def test_put_empty_body_is_valid(client):
    r = client.put("/api/v1/application-profile/", json={})
    assert r.status_code == 200
    assert r.json()["full_name"] is None
