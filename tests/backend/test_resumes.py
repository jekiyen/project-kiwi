"""Tests for the resume upload/library API endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _sa_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from tests.backend.test_resume_parser import make_minimal_docx, make_minimal_pdf

SAMPLE_TEXT = [
    "Jane Doe",
    "jane.doe@email.com",
    "+64 21 234 5678",
    "linkedin.com/in/janedoe",
    "",
    "Skills",
    "Python, SQL, Leadership",
    "",
    "Experience",
    "Data Analyst at Air NZ",
    "2019 - 2022",
    "- Built dashboards for ops reporting.",
    "",
    "Education",
    "University of Auckland, BSc Computer Science",
    "2015 - 2019",
]


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


@pytest.fixture(autouse=True)
def _resume_storage(tmp_path, monkeypatch):
    """Redirect uploaded files to a throwaway directory pytest cleans up."""
    from backend.config.settings import settings
    monkeypatch.setattr(settings, "resume_upload_dir", str(tmp_path / "resumes"))
    return tmp_path


@pytest.fixture
def client(_override_db):
    from backend.main import app
    return TestClient(app)


def _upload_pdf(client, filename="jane_doe.pdf", version_name=None, lines=None):
    pdf_bytes = make_minimal_pdf(lines if lines is not None else SAMPLE_TEXT)
    data = {"version_name": version_name} if version_name else {}
    return client.post(
        "/api/v1/resumes/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
        data=data,
    )


def _upload_docx(client, filename="jane_doe.docx", lines=None):
    docx_bytes = make_minimal_docx(lines if lines is not None else SAMPLE_TEXT)
    return client.post(
        "/api/v1/resumes/upload",
        files={"file": (filename, docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )


# ── Upload ────────────────────────────────────────────────────────────────────

def test_upload_pdf_creates_parsed_resume(client):
    r = _upload_pdf(client)
    assert r.status_code == 201
    data = r.json()
    assert data["file_type"] == "pdf"
    assert data["parse_status"] == "parsed"
    assert data["parser_version"] == "regex-v1"
    assert data["parsed_name"] == "Jane Doe"
    assert data["parsed_email"] == "jane.doe@email.com"
    assert "Python" in data["parsed_skills"]
    assert data["original_filename"] == "jane_doe.pdf"


def test_upload_docx_creates_parsed_resume(client):
    r = _upload_docx(client)
    assert r.status_code == 201
    data = r.json()
    assert data["file_type"] == "docx"
    assert data["parse_status"] == "parsed"
    assert data["parsed_email"] == "jane.doe@email.com"


def test_upload_uses_provided_version_name(client):
    r = _upload_pdf(client, version_name="Warehouse Application v2")
    assert r.json()["version_name"] == "Warehouse Application v2"


def test_upload_defaults_version_name_to_filename_stem(client):
    r = _upload_pdf(client, filename="my_cv.pdf")
    assert r.json()["version_name"] == "my_cv"


def test_upload_rejects_bad_extension(client):
    r = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("resume.txt", b"plain text resume", "text/plain")},
    )
    assert r.status_code == 400


def test_upload_rejects_empty_file(client):
    r = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert r.status_code == 400


def test_upload_rejects_oversized_file(client, monkeypatch):
    from backend.config.settings import settings
    monkeypatch.setattr(settings, "resume_max_file_size_mb", 1)
    oversized = b"x" * (2 * 1024 * 1024)
    r = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("huge.pdf", oversized, "application/pdf")},
    )
    assert r.status_code == 413


def test_upload_pdf_with_no_text_marks_failed_but_still_creates_row(client):
    r = _upload_pdf(client, lines=[])
    assert r.status_code == 201
    data = r.json()
    assert data["parse_status"] == "failed"
    assert data["parse_error"]
    assert data["parsed_skills"] == []


def test_upload_stores_file_on_disk(client, _resume_storage):
    _upload_pdf(client)
    stored_files = list((_resume_storage / "resumes").glob("*.pdf"))
    assert len(stored_files) == 1


# ── Active resume logic ──────────────────────────────────────────────────────

def test_first_upload_becomes_active_automatically(client):
    r = _upload_pdf(client)
    assert r.json()["is_active"] is True


def test_second_upload_is_not_active_by_default(client):
    _upload_pdf(client, filename="first.pdf")
    r = _upload_pdf(client, filename="second.pdf")
    assert r.json()["is_active"] is False


def test_activate_deactivates_others(client):
    first = _upload_pdf(client, filename="first.pdf").json()
    second = _upload_pdf(client, filename="second.pdf").json()
    assert first["is_active"] is True
    assert second["is_active"] is False

    r = client.post(f"/api/v1/resumes/{second['id']}/activate")
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    first_after = client.get(f"/api/v1/resumes/{first['id']}").json()
    assert first_after["is_active"] is False


def test_activate_nonexistent_returns_404(client):
    r = client.post("/api/v1/resumes/99999/activate")
    assert r.status_code == 404


# ── List / detail ────────────────────────────────────────────────────────────

def test_list_resumes_empty(client):
    r = client.get("/api/v1/resumes/")
    assert r.status_code == 200
    assert r.json() == []


def test_list_resumes_sorted_newest_first(client):
    _upload_pdf(client, filename="older.pdf")
    _upload_pdf(client, filename="newer.pdf")
    r = client.get("/api/v1/resumes/")
    names = [d["original_filename"] for d in r.json()]
    assert names[0] == "newer.pdf"


def test_get_resume_detail(client):
    created = _upload_pdf(client).json()
    r = client.get(f"/api/v1/resumes/{created['id']}")
    assert r.status_code == 200
    assert r.json()["raw_text"] is not None
    assert "Jane Doe" in r.json()["raw_text"]


def test_get_nonexistent_resume_returns_404(client):
    r = client.get("/api/v1/resumes/99999")
    assert r.status_code == 404


# ── Patch (rename + manual edits) ───────────────────────────────────────────

def test_patch_rename(client):
    created = _upload_pdf(client).json()
    r = client.patch(f"/api/v1/resumes/{created['id']}", json={"version_name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["version_name"] == "Renamed"


def test_patch_manual_field_corrections(client):
    created = _upload_pdf(client).json()
    r = client.patch(
        f"/api/v1/resumes/{created['id']}",
        json={
            "parsed_name": "Jane A. Doe",
            "parsed_skills": ["Python", "Leadership", "SQL"],
            "parsed_experience": [
                {"title": "Senior Analyst", "company": "Air NZ", "dates": "2019-2022", "description": "Fixed"}
            ],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["parsed_name"] == "Jane A. Doe"
    assert data["parsed_skills"] == ["Python", "Leadership", "SQL"]
    assert data["parsed_experience"][0]["title"] == "Senior Analyst"


def test_patch_nonexistent_resume_returns_404(client):
    r = client.patch("/api/v1/resumes/99999", json={"version_name": "X"})
    assert r.status_code == 404


def test_patch_does_not_touch_unspecified_fields(client):
    created = _upload_pdf(client).json()
    client.patch(f"/api/v1/resumes/{created['id']}", json={"version_name": "Renamed"})
    r = client.get(f"/api/v1/resumes/{created['id']}")
    assert r.json()["parsed_email"] == "jane.doe@email.com"  # untouched


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_removes_row(client):
    created = _upload_pdf(client).json()
    r = client.delete(f"/api/v1/resumes/{created['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/v1/resumes/{created['id']}").status_code == 404


def test_delete_removes_file_from_disk(client, _resume_storage):
    _upload_pdf(client)
    resume_dir = _resume_storage / "resumes"
    assert len(list(resume_dir.glob("*.pdf"))) == 1

    created = client.get("/api/v1/resumes/").json()[0]
    client.delete(f"/api/v1/resumes/{created['id']}")
    assert len(list(resume_dir.glob("*.pdf"))) == 0


def test_delete_nonexistent_resume_returns_404(client):
    r = client.delete("/api/v1/resumes/99999")
    assert r.status_code == 404
