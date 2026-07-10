import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from backend.config.settings import settings
from backend.database.models import Resume, ResumeResponse, ResumeUpdate
from backend.database.session import get_session

router = APIRouter(prefix="/resumes", tags=["resumes"])
logger = logging.getLogger("application")

_ALLOWED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx"}
_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _resume_dir() -> Path:
    d = Path(settings.resume_upload_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_or_404(session: Session, resume_id: int) -> Resume:
    resume = session.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


def _validate_upload(original_filename: str, data: bytes) -> str:
    """Validate an uploaded file and return its normalised file_type."""
    ext = Path(original_filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .pdf and .docx files are supported")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    max_bytes = settings.resume_max_file_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File is larger than the {settings.resume_max_file_size_mb}MB limit",
        )
    return _ALLOWED_EXTENSIONS[ext]


def _save_file(data: bytes, ext: str) -> str:
    """Save file bytes under a server-generated name and return it.

    The original filename is only ever used as display metadata — never
    trusted to build a file path.
    """
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    (_resume_dir() / stored_filename).write_bytes(data)
    return stored_filename


def _delete_file(stored_filename: str) -> None:
    path = _resume_dir() / stored_filename
    if path.exists():
        try:
            path.unlink()
        except OSError:
            logger.warning("Failed to delete resume file on disk: %s", path)


def _to_response(resume: Resume) -> ResumeResponse:
    return ResumeResponse(
        id=resume.id,
        original_filename=resume.original_filename,
        filename=resume.filename,
        file_type=resume.file_type,
        file_size=resume.file_size,
        is_active=resume.is_active,
        uploaded_at=resume.uploaded_at,
        updated_at=resume.updated_at,
    )


# ── List / detail ─────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ResumeResponse])
async def list_resumes(session: Session = Depends(get_session)) -> list[ResumeResponse]:
    resumes = session.exec(select(Resume).order_by(Resume.uploaded_at.desc())).all()
    return [_to_response(r) for r in resumes]


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(resume_id: int, session: Session = Depends(get_session)) -> ResumeResponse:
    return _to_response(_get_or_404(session, resume_id))


# ── Upload / replace ─────────────────────────────────────────────────────────

@router.post("/upload", response_model=ResumeResponse, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    filename: Optional[str] = Form(None),
    session: Session = Depends(get_session),
) -> ResumeResponse:
    """Store a PDF or DOCX resume. Kiwi doesn't parse or extract anything —
    the document itself is the source of truth (see docs/ROADMAP.md Phase 7.3)."""
    original_filename = file.filename or "resume"
    data = await file.read()
    ext = Path(original_filename).suffix.lower()
    file_type = _validate_upload(original_filename, data)
    stored_filename = _save_file(data, ext)

    resume = Resume(
        original_filename=original_filename,
        stored_filename=stored_filename,
        filename=(filename or Path(original_filename).stem).strip() or original_filename,
        file_type=file_type,
        file_size=len(data),
        is_active=False,
    )

    # First resume ever uploaded becomes active automatically — otherwise
    # nothing is active by default and the user has to remember to set one.
    resume_count = len(session.exec(select(Resume.id)).all())
    if resume_count == 0:
        resume.is_active = True

    session.add(resume)
    session.commit()
    session.refresh(resume)
    return _to_response(resume)


@router.post("/{resume_id}/replace", response_model=ResumeResponse)
async def replace_resume(
    resume_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> ResumeResponse:
    """Swap the stored document for an existing vault entry — same id, same
    display name and active status, new file."""
    resume = _get_or_404(session, resume_id)

    original_filename = file.filename or "resume"
    data = await file.read()
    ext = Path(original_filename).suffix.lower()
    file_type = _validate_upload(original_filename, data)
    new_stored_filename = _save_file(data, ext)

    old_stored_filename = resume.stored_filename
    resume.stored_filename = new_stored_filename
    resume.original_filename = original_filename
    resume.file_type = file_type
    resume.file_size = len(data)
    resume.updated_at = datetime.utcnow()
    session.add(resume)
    session.commit()
    session.refresh(resume)

    _delete_file(old_stored_filename)
    return _to_response(resume)


# ── Active resume ────────────────────────────────────────────────────────────

@router.post("/{resume_id}/activate", response_model=ResumeResponse)
async def activate_resume(resume_id: int, session: Session = Depends(get_session)) -> ResumeResponse:
    """Mark this resume active and deactivate every other one — exactly one
    resume is active at a time."""
    resume = _get_or_404(session, resume_id)

    others = session.exec(
        select(Resume).where(Resume.id != resume_id, Resume.is_active == True)  # noqa: E712
    ).all()
    for other in others:
        other.is_active = False
        other.updated_at = datetime.utcnow()
        session.add(other)

    resume.is_active = True
    resume.updated_at = datetime.utcnow()
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return _to_response(resume)


# ── Rename ────────────────────────────────────────────────────────────────────

@router.patch("/{resume_id}", response_model=ResumeResponse)
async def update_resume(
    resume_id: int,
    body: ResumeUpdate,
    session: Session = Depends(get_session),
) -> ResumeResponse:
    resume = _get_or_404(session, resume_id)

    if body.filename is not None:
        resume.filename = body.filename

    resume.updated_at = datetime.utcnow()
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return _to_response(resume)


# ── File access ───────────────────────────────────────────────────────────────

def _file_response(resume: Resume, disposition: str) -> FileResponse:
    path = _resume_dir() / resume.stored_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Resume file is missing from disk")
    return FileResponse(
        path,
        media_type=_MEDIA_TYPES.get(resume.file_type, "application/octet-stream"),
        filename=resume.original_filename,
        content_disposition_type=disposition,
    )


@router.get("/{resume_id}/preview")
async def preview_resume(resume_id: int, session: Session = Depends(get_session)) -> FileResponse:
    return _file_response(_get_or_404(session, resume_id), "inline")


@router.get("/{resume_id}/download")
async def download_resume(resume_id: int, session: Session = Depends(get_session)) -> FileResponse:
    return _file_response(_get_or_404(session, resume_id), "attachment")


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{resume_id}", status_code=204)
async def delete_resume(resume_id: int, session: Session = Depends(get_session)) -> None:
    resume = _get_or_404(session, resume_id)
    stored_filename = resume.stored_filename
    session.delete(resume)
    session.commit()
    _delete_file(stored_filename)
