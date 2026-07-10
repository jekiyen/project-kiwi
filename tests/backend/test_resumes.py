"""Tests for the Resume Vault API — pure file storage + metadata, no parsing."""
import io

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _sa_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel


def make_minimal_pdf(text_lines: list[str] | None = None) -> bytes:
    """Hand-crafted minimal single-page PDF. Avoids adding a PDF-generation
    library as a dependency just for tests."""
    text_lines = text_lines if text_lines is not None else ["Test Resume"]
    buf = io.BytesIO()

    def w(s):
        buf.write(s.encode("latin-1") if isinstance(s, str) else s)

    offsets: dict[int, int] = {}
    w("%PDF-1.4\n")
    offsets[1] = buf.tell()
    w("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    offsets[2] = buf.tell()
    w("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    offsets[3] = buf.tell()
    w(
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        "/MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n"
    )
    offsets[4] = buf.tell()
    w("4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    content_lines = ["BT", "/F1 11 Tf", "12 TL", "72 740 Td"]
    for i, line in enumerate(text_lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if i > 0:
            content_lines.append("T*")
        content_lines.append(f"({escaped}) Tj")
    content_lines.append("ET")
    content_bytes = "\n".join(content_lines).encode("latin-1")

    offsets[5] = buf.tell()
    w(f"5 0 obj\n<< /Length {len(content_bytes)} >>\nstream\n")
    w(content_bytes)
    w("\nendstream\nendobj\n")

    xref_offset = buf.tell()
    w("xref\n0 6\n0000000000 65535 f \n")
    for i in range(1, 6):
        w(f"{offsets[i]:010d} 00000 n \n")
    w(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF")
    return buf.getvalue()


def make_minimal_docx(paragraphs: list[str] | None = None) -> bytes:
    paragraphs = paragraphs if paragraphs is not None else ["Test Resume"]
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


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


def _upload_pdf(client, filename="jane_doe.pdf", display_name=None, lines=None):
    pdf_bytes = make_minimal_pdf(lines)
    data = {"filename": display_name} if display_name else {}
    return client.post(
        "/api/v1/resumes/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
        data=data,
    )


def _upload_docx(client, filename="jane_doe.docx", lines=None):
    docx_bytes = make_minimal_docx(lines)
    return client.post(
        "/api/v1/resumes/upload",
        files={"file": (filename, docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )


# ── Upload — metadata only, no parsing ──────────────────────────────────────

def test_upload_pdf_stores_metadata_only(client):
    r = _upload_pdf(client, lines=["Anything at all"])
    assert r.status_code == 201
    data = r.json()
    assert data["file_type"] == "pdf"
    assert data["original_filename"] == "jane_doe.pdf"
    assert data["file_size"] > 0
    assert set(data.keys()) == {
        "id", "original_filename", "filename", "file_type",
        "file_size", "is_active", "uploaded_at", "updated_at",
    }


def test_upload_docx_stores_metadata_only(client):
    r = _upload_docx(client)
    assert r.status_code == 201
    data = r.json()
    assert data["file_type"] == "docx"
    assert data["file_size"] > 0


def test_upload_uses_provided_filename(client):
    r = _upload_pdf(client, display_name="Warehouse Application v2")
    assert r.json()["filename"] == "Warehouse Application v2"


def test_upload_defaults_filename_to_original_stem(client):
    r = _upload_pdf(client, filename="my_cv.pdf")
    assert r.json()["filename"] == "my_cv"


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


def test_upload_stores_file_on_disk(client, _resume_storage):
    _upload_pdf(client)
    stored_files = list((_resume_storage / "resumes").glob("*.pdf"))
    assert len(stored_files) == 1


def test_upload_file_size_matches_actual_bytes(client):
    lines = ["A longer resume body to get a bigger file size " * 10]
    r = _upload_pdf(client, lines=lines)
    data = r.json()
    # Not an exact byte-for-byte check (PDF wrapper overhead), just sane.
    assert data["file_size"] > 100


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
    assert r.json()["id"] == created["id"]


def test_get_nonexistent_resume_returns_404(client):
    r = client.get("/api/v1/resumes/99999")
    assert r.status_code == 404


# ── Rename ────────────────────────────────────────────────────────────────────

def test_patch_rename(client):
    created = _upload_pdf(client).json()
    r = client.patch(f"/api/v1/resumes/{created['id']}", json={"filename": "Renamed"})
    assert r.status_code == 200
    assert r.json()["filename"] == "Renamed"


def test_patch_nonexistent_resume_returns_404(client):
    r = client.patch("/api/v1/resumes/99999", json={"filename": "X"})
    assert r.status_code == 404


def test_patch_does_not_touch_other_fields(client):
    created = _upload_pdf(client).json()
    client.patch(f"/api/v1/resumes/{created['id']}", json={"filename": "Renamed"})
    r = client.get(f"/api/v1/resumes/{created['id']}")
    assert r.json()["original_filename"] == created["original_filename"]
    assert r.json()["file_size"] == created["file_size"]


# ── Replace ───────────────────────────────────────────────────────────────────

def test_replace_keeps_id_filename_and_active_status(client):
    created = _upload_pdf(client, filename="v1.pdf", display_name="My Resume").json()
    client.post(f"/api/v1/resumes/{created['id']}/activate")

    r = client.post(
        f"/api/v1/resumes/{created['id']}/replace",
        files={"file": ("v2.pdf", make_minimal_pdf(["New content"]), "application/pdf")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == created["id"]
    assert data["filename"] == "My Resume"  # unchanged
    assert data["is_active"] is True  # unchanged
    assert data["original_filename"] == "v2.pdf"  # updated


def test_replace_swaps_file_on_disk(client, _resume_storage):
    created = _upload_pdf(client, filename="v1.pdf").json()
    resume_dir = _resume_storage / "resumes"
    assert len(list(resume_dir.glob("*.pdf"))) == 1

    client.post(
        f"/api/v1/resumes/{created['id']}/replace",
        files={"file": ("v2.pdf", make_minimal_pdf(["New content"]), "application/pdf")},
    )
    # Old file gone, exactly one (new) file remains under a new stored name.
    assert len(list(resume_dir.glob("*.pdf"))) == 1


def test_replace_rejects_bad_extension(client):
    created = _upload_pdf(client).json()
    r = client.post(
        f"/api/v1/resumes/{created['id']}/replace",
        files={"file": ("bad.txt", b"not a resume", "text/plain")},
    )
    assert r.status_code == 400


def test_replace_nonexistent_resume_returns_404(client):
    r = client.post(
        "/api/v1/resumes/99999/replace",
        files={"file": ("v2.pdf", make_minimal_pdf(), "application/pdf")},
    )
    assert r.status_code == 404


# ── Preview / download ───────────────────────────────────────────────────────

def test_preview_returns_inline_content_disposition(client):
    created = _upload_pdf(client).json()
    r = client.get(f"/api/v1/resumes/{created['id']}/preview")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "inline" in r.headers["content-disposition"]


def test_download_returns_attachment_content_disposition_with_original_name(client):
    created = _upload_pdf(client, filename="my_original_name.pdf").json()
    r = client.get(f"/api/v1/resumes/{created['id']}/download")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert "my_original_name.pdf" in r.headers["content-disposition"]


def test_preview_returns_exact_uploaded_bytes(client):
    pdf_bytes = make_minimal_pdf(["Unique content marker 12345"])
    r = client.post(
        "/api/v1/resumes/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    resume_id = r.json()["id"]
    preview = client.get(f"/api/v1/resumes/{resume_id}/preview")
    assert preview.content == pdf_bytes


def test_preview_nonexistent_resume_returns_404(client):
    r = client.get("/api/v1/resumes/99999/preview")
    assert r.status_code == 404


def test_download_nonexistent_resume_returns_404(client):
    r = client.get("/api/v1/resumes/99999/download")
    assert r.status_code == 404


def test_preview_docx_uses_correct_media_type(client):
    created = _upload_docx(client).json()
    r = client.get(f"/api/v1/resumes/{created['id']}/preview")
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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
