import json
import logging
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from backend.config.settings import settings
from backend.database.models import (
    Resume,
    ResumeParseStatus,
    ResumeResponse,
    ResumeUpdate,
)
from backend.database.session import get_session
from backend.resume import get_resume_parser
from backend.resume.text_extraction import TextExtractionError, extract_text

router = APIRouter(prefix="/resumes", tags=["resumes"])
logger = logging.getLogger("application")

_ALLOWED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx"}


def _resume_dir() -> Path:
    d = Path(settings.resume_upload_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _to_response(resume: Resume) -> ResumeResponse:
    return ResumeResponse(
        id=resume.id,
        original_filename=resume.original_filename,
        version_name=resume.version_name,
        file_type=resume.file_type,
        is_active=resume.is_active,
        parse_status=resume.parse_status,
        parser_version=resume.parser_version,
        parse_error=resume.parse_error,
        uploaded_at=resume.uploaded_at,
        updated_at=resume.updated_at,
        raw_text=resume.raw_text,
        parsed_name=resume.parsed_name,
        parsed_email=resume.parsed_email,
        parsed_phone=resume.parsed_phone,
        parsed_linkedin=resume.parsed_linkedin,
        parsed_portfolio=resume.parsed_portfolio,
        parsed_skills=json.loads(resume.parsed_skills) if resume.parsed_skills else [],
        parsed_companies=json.loads(resume.parsed_companies) if resume.parsed_companies else [],
        parsed_job_titles=json.loads(resume.parsed_job_titles) if resume.parsed_job_titles else [],
        parsed_education=json.loads(resume.parsed_education) if resume.parsed_education else [],
        parsed_experience=json.loads(resume.parsed_experience) if resume.parsed_experience else [],
    )


@router.get("/", response_model=list[ResumeResponse])
async def list_resumes(session: Session = Depends(get_session)) -> list[ResumeResponse]:
    resumes = session.exec(select(Resume).order_by(Resume.uploaded_at.desc())).all()
    return [_to_response(r) for r in resumes]


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(resume_id: int, session: Session = Depends(get_session)) -> ResumeResponse:
    resume = session.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return _to_response(resume)


@router.post("/upload", response_model=ResumeResponse, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    version_name: str | None = Form(None),
    session: Session = Depends(get_session),
) -> ResumeResponse:
    """Upload a PDF or DOCX resume. Extracts text and parses it synchronously —
    resumes are small enough that this stays fast, and the user sees the
    result immediately instead of having to poll."""
    original_filename = file.filename or "resume"
    ext = Path(original_filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .pdf and .docx files are supported")
    file_type = _ALLOWED_EXTENSIONS[ext]

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    max_bytes = settings.resume_max_file_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File is larger than the {settings.resume_max_file_size_mb}MB limit",
        )

    # Stored under a server-generated name — the original filename is only
    # ever used as display metadata, never trusted to build a file path.
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    dest = _resume_dir() / stored_filename
    dest.write_bytes(data)

    resume = Resume(
        original_filename=original_filename,
        stored_filename=stored_filename,
        version_name=(version_name or Path(original_filename).stem).strip() or original_filename,
        file_type=file_type,
        is_active=False,
    )

    try:
        text = extract_text(data, file_type)
        parser = get_resume_parser()
        parsed = await parser.parse(text)

        resume.raw_text = text
        resume.parsed_name = parsed.name
        resume.parsed_email = parsed.email
        resume.parsed_phone = parsed.phone
        resume.parsed_linkedin = parsed.linkedin
        resume.parsed_portfolio = parsed.portfolio
        resume.parsed_skills = json.dumps(parsed.skills)
        resume.parsed_companies = json.dumps(parsed.companies)
        resume.parsed_job_titles = json.dumps(parsed.job_titles)
        resume.parsed_education = json.dumps([asdict(e) for e in parsed.education])
        resume.parsed_experience = json.dumps([asdict(e) for e in parsed.experience])
        resume.parse_status = ResumeParseStatus.PARSED
        resume.parser_version = parser.version
    except TextExtractionError as exc:
        resume.parse_status = ResumeParseStatus.FAILED
        resume.parse_error = str(exc)
        resume.parser_version = get_resume_parser().version
    except Exception as exc:
        logger.exception("Unexpected error parsing uploaded resume %s", original_filename)
        resume.parse_status = ResumeParseStatus.FAILED
        resume.parse_error = f"Unexpected error while parsing: {exc}"

    # First resume ever uploaded becomes active automatically — otherwise
    # nothing is active by default and the user has to remember to set one.
    resume_count = len(session.exec(select(Resume.id)).all())
    if resume_count == 0:
        resume.is_active = True

    session.add(resume)
    session.commit()
    session.refresh(resume)
    return _to_response(resume)


@router.post("/{resume_id}/activate", response_model=ResumeResponse)
async def activate_resume(resume_id: int, session: Session = Depends(get_session)) -> ResumeResponse:
    """Mark this resume active and deactivate every other one — exactly one
    resume is active at a time."""
    resume = session.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

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


@router.patch("/{resume_id}", response_model=ResumeResponse)
async def update_resume(
    resume_id: int,
    body: ResumeUpdate,
    session: Session = Depends(get_session),
) -> ResumeResponse:
    """Rename a resume or manually correct fields the parser got wrong."""
    resume = session.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if body.version_name is not None:
        resume.version_name = body.version_name
    if body.parsed_name is not None:
        resume.parsed_name = body.parsed_name
    if body.parsed_email is not None:
        resume.parsed_email = body.parsed_email
    if body.parsed_phone is not None:
        resume.parsed_phone = body.parsed_phone
    if body.parsed_linkedin is not None:
        resume.parsed_linkedin = body.parsed_linkedin
    if body.parsed_portfolio is not None:
        resume.parsed_portfolio = body.parsed_portfolio
    if body.parsed_skills is not None:
        resume.parsed_skills = json.dumps(body.parsed_skills)
    if body.parsed_companies is not None:
        resume.parsed_companies = json.dumps(body.parsed_companies)
    if body.parsed_job_titles is not None:
        resume.parsed_job_titles = json.dumps(body.parsed_job_titles)
    if body.parsed_education is not None:
        resume.parsed_education = json.dumps(body.parsed_education)
    if body.parsed_experience is not None:
        resume.parsed_experience = json.dumps(body.parsed_experience)

    resume.updated_at = datetime.utcnow()
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return _to_response(resume)


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(resume_id: int, session: Session = Depends(get_session)) -> None:
    resume = session.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    file_path = _resume_dir() / resume.stored_filename
    session.delete(resume)
    session.commit()

    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            logger.warning("Failed to delete resume file on disk: %s", file_path)
