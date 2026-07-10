import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlmodel import Session, select

from backend.ai import get_ai_provider
from backend.config.user_profile import USER_PROFILE
from backend.database.models import Application, ApplicationStatus, Job
from backend.database.queries import log_application_event
from backend.database.session import get_session

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/")
async def list_jobs(
    session: Session = Depends(get_session),
    limit: int = Query(50, le=200),
    offset: int = 0,
    active_only: bool = True,
) -> list[Job]:
    stmt = select(Job)
    if active_only:
        stmt = stmt.where(Job.is_active == True)  # noqa: E712
    stmt = stmt.order_by(Job.ai_match_score.desc(), Job.first_seen_at.desc())
    stmt = stmt.offset(offset).limit(limit)
    return list(session.exec(stmt).all())


@router.get("/{job_id}")
async def get_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/analyse")
async def analyse_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    """Score a single job immediately. Always rescores regardless of prior analysis."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    provider = get_ai_provider()
    job_data = {
        "title": job.title,
        "employer": job.employer,
        "location": job.location,
        "description": job.description or "",
        "salary_text": job.salary_text or "",
    }
    analysis = await provider.analyze_job(job_data, USER_PROFILE)

    job.ai_match_score = analysis.score
    job.ai_explanation = analysis.explanation
    job.visa_accredited_employer = analysis.visa_accredited_employer
    job.visa_overseas_friendly = analysis.visa_overseas_friendly
    job.visa_sponsorship_potential = analysis.visa_sponsorship_potential
    job.visa_nz_rights_required = analysis.visa_nz_rights_required
    job.ai_priority = analysis.priority
    job.ai_reasons = json.dumps(analysis.reasons)
    job.ai_pros = json.dumps(analysis.pros)
    job.ai_cons = json.dumps(analysis.cons)
    job.ai_visa_probability = analysis.visa_probability
    job.ai_confidence = analysis.confidence
    job.ai_provider = analysis.provider
    job.ai_model = analysis.model
    job.ai_analysed_at = datetime.utcnow()

    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.post("/{job_id}/save")
async def save_job(job_id: int, session: Session = Depends(get_session)) -> Application:
    """Save a job. Idempotent — returns the existing application if one already exists."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    existing = session.exec(
        select(Application).where(Application.job_id == job_id)
    ).first()
    if existing:
        return existing
    app = Application(job_id=job_id, status=ApplicationStatus.SAVED)
    session.add(app)
    session.commit()
    session.refresh(app)
    log_application_event(session, app.id, "created", to_status=app.status)
    session.commit()
    session.refresh(app)
    return app


@router.post("/{job_id}/apply")
async def apply_to_job(job_id: int, session: Session = Depends(get_session)) -> Application:
    """Mark a job as applied. Creates the application if it doesn't exist."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    app = session.exec(
        select(Application).where(Application.job_id == job_id)
    ).first()
    is_new = app is None
    if app is None:
        app = Application(job_id=job_id)
    previous_status = app.status
    app.status = ApplicationStatus.APPLIED
    if app.applied_at is None:
        app.applied_at = datetime.utcnow()
    app.updated_at = datetime.utcnow()
    session.add(app)
    session.commit()
    session.refresh(app)
    if is_new:
        log_application_event(session, app.id, "created", to_status=app.status)
    elif previous_status != app.status:
        log_application_event(
            session, app.id, "status_change", from_status=previous_status, to_status=app.status
        )
    session.commit()
    session.refresh(app)
    return app


@router.post("/analyse-pending")
async def analyse_pending(
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Rescore jobs that have already been analysed"),
) -> dict:
    """Queue analysis for unscored jobs. Pass ?force=true to rescore all jobs."""
    from backend.agents.scan_agent import ScanAgent
    agent = ScanAgent()
    background_tasks.add_task(agent._analyze_pending, 0, force)
    verb = "all" if force else "unscored"
    return {"message": f"Analysis queued for {verb} jobs"}
