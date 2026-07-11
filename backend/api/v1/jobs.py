import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.ai import get_ai_provider
from backend.api.v1.common import MessageResponse
from backend.config.user_profile import USER_PROFILE
from backend.core.ai_readiness import ReadinessStatus, evaluate_ai_readiness
from backend.database.models import Application, ApplicationStatus, Job, JobChange, Resume
from backend.database.queries import log_application_event
from backend.database.session import get_session
from backend.notifications import NotificationEvent, NotificationEventType, notification_service
from backend.prompt_engine import get_action, render_template

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _dispatch_application_created(background_tasks: BackgroundTasks, job: Job, app: Application) -> None:
    background_tasks.add_task(
        notification_service.dispatch,
        NotificationEvent(
            type=NotificationEventType.APPLICATION_CREATED,
            data={"title": job.title, "employer": job.employer, "status": app.status.value},
        ),
    )


def _dispatch_application_status_changed(
    background_tasks: BackgroundTasks, job: Job, app: Application, previous_status: ApplicationStatus
) -> None:
    background_tasks.add_task(
        notification_service.dispatch,
        NotificationEvent(
            type=NotificationEventType.APPLICATION_STATUS_CHANGED,
            data={
                "title": job.title,
                "employer": job.employer,
                "from_status": previous_status.value,
                "to_status": app.status.value,
            },
        ),
    )


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


class JobUpdate(BaseModel):
    """Fields editable via the AI Workspace's "Edit Job" fast path — filling
    these in is what moves a job from Partial/Not Ready to Ready."""
    title: str | None = None
    employer: str | None = None
    location: str | None = None
    description: str | None = None


@router.patch("/{job_id}")
async def update_job(job_id: int, body: JobUpdate, session: Session = Depends(get_session)) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    changes = body.model_dump(exclude_unset=True)
    for field_name, new_value in changes.items():
        old_value = getattr(job, field_name)
        if old_value != new_value:
            session.add(JobChange(
                job_id=job.id,
                field_changed=field_name,
                old_value=str(old_value) if old_value is not None else None,
                new_value=str(new_value) if new_value is not None else None,
            ))
        setattr(job, field_name, new_value)

    session.add(job)
    session.commit()
    session.refresh(job)
    return job


class AIReadinessResponse(BaseModel):
    status: str
    missing: list[str]
    impact: str


@router.get("/{job_id}/ai-readiness", response_model=AIReadinessResponse)
async def get_job_ai_readiness(job_id: int, session: Session = Depends(get_session)) -> AIReadinessResponse:
    """Powers the AI Workspace's readiness card. Uses the same evaluator as
    the Prompt Guard in generate_job_prompt below, so the two can never
    disagree about whether a job is ready for AI generation."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    active_resume = session.exec(select(Resume).where(Resume.is_active == True)).first()  # noqa: E712
    readiness = evaluate_ai_readiness(job, active_resume)
    return AIReadinessResponse(status=readiness.status.value, missing=readiness.missing, impact=readiness.impact)


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
async def save_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> Application:
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
    session.flush()  # assigns app.id without ending the transaction
    log_application_event(session, app.id, "created", to_status=app.status)
    session.commit()  # app + its "created" event land atomically together
    session.refresh(app)
    _dispatch_application_created(background_tasks, job, app)
    return app


@router.post("/{job_id}/apply")
async def apply_to_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> Application:
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
    status_changed = previous_status != ApplicationStatus.APPLIED
    app.status = ApplicationStatus.APPLIED
    if app.applied_at is None:
        app.applied_at = datetime.utcnow()
    app.updated_at = datetime.utcnow()
    session.add(app)
    session.flush()  # assigns app.id without ending the transaction

    if is_new:
        log_application_event(session, app.id, "created", to_status=app.status)
    elif status_changed:
        log_application_event(
            session, app.id, "status_change", from_status=previous_status, to_status=app.status
        )
    session.commit()  # app + its event land atomically together
    session.refresh(app)

    if is_new:
        _dispatch_application_created(background_tasks, job, app)
    elif status_changed:
        _dispatch_application_status_changed(background_tasks, job, app, previous_status)
    return app


class GeneratedPrompt(BaseModel):
    title: str
    content: str
    readiness_status: str
    disclaimer: str | None = None


_MISSING_DESCRIPTION_GUARD = (
    "No job description was provided. Base your analysis only on the job title, "
    "company, and location below — do not invent or assume any responsibilities, "
    "requirements, or qualifications that aren't explicitly stated. Clearly note "
    "in your response that this analysis has limited confidence because the job "
    "description is missing."
)


@router.get("/{job_id}/prompts/{action_id}", response_model=GeneratedPrompt)
async def generate_job_prompt(
    job_id: int, action_id: str, session: Session = Depends(get_session)
) -> GeneratedPrompt:
    """Render a prompt for this job using the Prompt Engine. Returns plain text
    for the user to copy and paste into Claude by hand — no AI call happens here.

    Prompt Guard: blocks generation entirely when AI Readiness is Not Ready
    (missing job title/company/active resume), and injects an explicit
    anti-hallucination instruction + a UI disclaimer when Partial (missing
    job description) so confidence stays honest instead of silently guessing.
    """
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    action = get_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Unknown AI action")

    active_resume = session.exec(select(Resume).where(Resume.is_active == True)).first()  # noqa: E712
    readiness = evaluate_ai_readiness(job, active_resume)

    if readiness.status == ReadinessStatus.NOT_READY:
        raise HTTPException(
            status_code=409,
            detail=f"AI Readiness: Not Ready — missing {', '.join(readiness.missing)}. "
                   "Add this information before generating a prompt.",
        )

    resume_name = active_resume.filename if active_resume else "No active resume — set one in the Resume Vault"
    disclaimer: str | None = None
    if job.description:
        job_description_text = job.description
    else:
        job_description_text = _MISSING_DESCRIPTION_GUARD
        disclaimer = (
            "Job Description is missing — this prompt has limited context and "
            "AI confidence will be lower."
        )

    variables = {
        "resume_name": resume_name,
        "job_title": job.title,
        "company_name": job.employer,
        "job_description": job_description_text,
        "job_location": job.location,
        "employment_type": "Not specified",
    }

    content = render_template(action.template_file, variables)
    return GeneratedPrompt(
        title=action.label, content=content, readiness_status=readiness.status.value, disclaimer=disclaimer
    )


@router.get("/{job_id}/changes", response_model=list[JobChange])
async def get_job_changes(job_id: int, session: Session = Depends(get_session)) -> list[JobChange]:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return list(session.exec(
        select(JobChange).where(JobChange.job_id == job_id).order_by(JobChange.detected_at.desc())
    ).all())


@router.post("/analyse-pending", response_model=MessageResponse, status_code=202)
async def analyse_pending(
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Rescore jobs that have already been analysed"),
) -> MessageResponse:
    """Queue analysis for unscored jobs. Pass ?force=true to rescore all jobs."""
    from backend.agents.scan_agent import ScanAgent
    agent = ScanAgent()
    background_tasks.add_task(agent._analyze_pending, 0, force)
    verb = "all" if force else "unscored"
    return MessageResponse(message=f"Analysis queued for {verb} jobs")
