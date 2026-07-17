import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.ai import get_ai_provider
from backend.api.v1.common import MessageResponse
from backend.config.user_profile import USER_PROFILE
from backend.core.ai_readiness import ReadinessStatus, evaluate_ai_readiness
from backend.core.application_readiness import (
    ApplicationReadiness,
    evaluate_application_readiness,
)
from backend.core.job_intelligence import evaluate_job_intelligence, find_similar_jobs
from backend.core.listing_url import build_fallback_link, is_exact_listing_url
from backend.database.models import (
    Application,
    ApplicationKitResponse,
    ApplicationProfile,
    ApplicationReadinessResponse,
    ApplicationReference,
    ApplicationSession,
    ApplicationSessionResponse,
    ApplicationSessionStatus,
    ApplicationStatus,
    CompleteSessionRequest,
    CompleteSessionResponse,
    Job,
    JobChange,
    JobIntelligenceResponse,
    JobIntelligenceSummaryItem,
    LaunchApplicationResponse,
    Resume,
    SectionReadinessOut,
    SimilarJobResponse,
)
from backend.database.queries import get_active_session, log_application_event
from backend.database.session import get_session
from backend.job_summary import JobSummary, load_job_summary, render_summary_as_text, summarize_job
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


# ── Application Copilot (Phase 8) — Readiness Engine ─────────────────────────
# backend/core/application_readiness.py is the single evaluator; every
# endpoint below is a thin wrapper around it — never re-implement the rules.

def _evaluate_job_readiness(session: Session, job: Job) -> ApplicationReadiness:
    profile = session.exec(select(ApplicationProfile)).first()
    references = (
        list(session.exec(
            select(ApplicationReference).where(ApplicationReference.profile_id == profile.id)
        ).all())
        if profile
        else []
    )
    active_resume = session.exec(select(Resume).where(Resume.is_active == True)).first()  # noqa: E712
    return evaluate_application_readiness(job, profile, references, active_resume)


def _readiness_to_response(readiness: ApplicationReadiness) -> ApplicationReadinessResponse:
    return ApplicationReadinessResponse(
        status=readiness.status.value,
        sections=SectionReadinessOut(
            resume=readiness.sections.resume,
            application_profile=readiness.sections.application_profile,
            cover_letter=readiness.sections.cover_letter,
            references=readiness.sections.references,
            work_rights=readiness.sections.work_rights,
        ),
        missing=readiness.missing,
        score=readiness.score,
        estimated_minutes=readiness.estimated_minutes,
    )


@router.get("/readiness-summary")
async def get_readiness_summary(session: Session = Depends(get_session)) -> dict[str, str]:
    """Bulk Application Readiness status for every active job, in one query
    round trip — powers the Dashboard's Ready/Preparing badges. Application
    Profile, references, and active resume are shared across every job and
    fetched once; only Job.cover_letter_generated_at varies per job."""
    profile = session.exec(select(ApplicationProfile)).first()
    references = (
        list(session.exec(
            select(ApplicationReference).where(ApplicationReference.profile_id == profile.id)
        ).all())
        if profile
        else []
    )
    active_resume = session.exec(select(Resume).where(Resume.is_active == True)).first()  # noqa: E712
    jobs = session.exec(select(Job).where(Job.is_active == True)).all()  # noqa: E712

    return {
        str(job.id): evaluate_application_readiness(job, profile, references, active_resume).status.value
        for job in jobs
    }


@router.get("/{job_id}/application-readiness", response_model=ApplicationReadinessResponse)
async def get_job_application_readiness(
    job_id: int, session: Session = Depends(get_session)
) -> ApplicationReadinessResponse:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _readiness_to_response(_evaluate_job_readiness(session, job))


# ── Job Intelligence (Phase 9) ────────────────────────────────────────────────
# backend/core/job_intelligence.py is the single evaluator — every endpoint
# below is a thin wrapper; never re-implement scoring or recommendation rules.

def _job_intelligence_response(job: Job, session: Session) -> JobIntelligenceResponse:
    had_summary = bool(job.summary_json)
    summary = load_job_summary(job)
    if not had_summary:
        session.add(job)  # load_job_summary generated one on the fly — persist it
    intelligence = evaluate_job_intelligence(job, summary)
    return JobIntelligenceResponse(
        score=intelligence.score,
        confidence=intelligence.confidence,
        recommendation=intelligence.recommendation.value,
        reasons=intelligence.reasons,
        missing_requirements=intelligence.missing_requirements,
    )


@router.get("/job-intelligence-summary")
async def get_job_intelligence_summary(
    session: Session = Depends(get_session),
) -> dict[str, JobIntelligenceSummaryItem]:
    """Bulk Job Intelligence score/recommendation for every active job, in
    one query round trip — powers the Dashboard's Priority Queue sort and
    the High Match / Ready / Visa Compatible filters."""
    jobs = session.exec(select(Job).where(Job.is_active == True)).all()  # noqa: E712
    result: dict[str, JobIntelligenceSummaryItem] = {}
    dirty = False
    for job in jobs:
        had_summary = bool(job.summary_json)
        summary = load_job_summary(job)
        if not had_summary:
            session.add(job)
            dirty = True
        intelligence = evaluate_job_intelligence(job, summary)
        result[str(job.id)] = JobIntelligenceSummaryItem(
            score=intelligence.score, recommendation=intelligence.recommendation.value
        )
    if dirty:
        session.commit()
    return result


@router.get("/{job_id}/job-intelligence", response_model=JobIntelligenceResponse)
async def get_job_intelligence(
    job_id: int, session: Session = Depends(get_session)
) -> JobIntelligenceResponse:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    response = _job_intelligence_response(job, session)
    session.commit()
    return response


@router.get("/{job_id}/similar", response_model=list[SimilarJobResponse])
async def get_similar_jobs(job_id: int, session: Session = Depends(get_session)) -> list[SimilarJobResponse]:
    """Deterministic similarity by Title, Industry (role_priority — the
    closest proxy Kiwi has), and Location. See find_similar_jobs()."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    candidates = session.exec(
        select(Job).where(Job.is_active == True, Job.id != job_id)  # noqa: E712
    ).all()
    similar = find_similar_jobs(job, candidates)
    return [
        SimilarJobResponse(
            id=s.job.id,
            title=s.job.title,
            employer=s.job.employer,
            location=s.job.location,
            source=s.job.source,
            ai_match_score=s.job.ai_match_score,
            similarity_score=s.similarity_score,
        )
        for s in similar
    ]


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
    description_changed = False
    for field_name, new_value in changes.items():
        old_value = getattr(job, field_name)
        if old_value != new_value:
            session.add(JobChange(
                job_id=job.id,
                field_changed=field_name,
                old_value=str(old_value) if old_value is not None else None,
                new_value=str(new_value) if new_value is not None else None,
            ))
            if field_name == "description":
                description_changed = True
        setattr(job, field_name, new_value)

    if description_changed:
        summarize_job(job)  # never touches job.description itself

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


@router.get("/{job_id}/summary", response_model=JobSummary)
async def get_job_summary(job_id: int, session: Session = Depends(get_session)) -> JobSummary:
    """The structured Kiwi Job Summary — deterministic, no LLM. Jobs created
    before Phase 7.6 don't have one stored yet; generated and persisted here
    on first read so every job has one going forward."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    had_summary = bool(job.summary_json)
    summary = load_job_summary(job)
    if not had_summary:
        session.add(job)
        session.commit()
    return summary


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


# ── Application Copilot (Phase 8) — Application Kit / Launch / Sessions ──────
# Kiwi assists, the user submits: launch only ever hands back the original
# job URL for the frontend to open in a new tab. It never submits anything,
# clicks anything, or uploads anything on the employer's site.

def _session_to_response(sess: ApplicationSession) -> ApplicationSessionResponse:
    end = sess.completed_at or datetime.utcnow()
    return ApplicationSessionResponse(
        id=sess.id,
        application_id=sess.application_id,
        status=sess.status,
        started_at=sess.started_at,
        last_opened_at=sess.last_opened_at,
        completed_at=sess.completed_at,
        duration_seconds=int((end - sess.started_at).total_seconds()),
        resume_version=sess.resume_version,
        cover_letter_version=sess.cover_letter_version,
        profile_version=sess.profile_version,
    )


@router.get("/{job_id}/application-kit", response_model=ApplicationKitResponse)
async def get_application_kit(job_id: int, session: Session = Depends(get_session)) -> ApplicationKitResponse:
    """Everything the Application Kit needs in one call: Application
    Readiness, the Application record (if one exists yet), and the current
    in-progress session (if the user has launched and not yet confirmed an
    outcome)."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    readiness = _evaluate_job_readiness(session, job)
    app = session.exec(select(Application).where(Application.job_id == job_id)).first()
    active_session = get_active_session(session, app.id) if app else None

    exact = is_exact_listing_url(job.source, job.url)
    fallback_link: str | None = None
    fallback_is_search = False
    if not exact:
        link, is_search = build_fallback_link(job.source, job.title)
        fallback_link = link or None
        fallback_is_search = is_search

    return ApplicationKitResponse(
        readiness=_readiness_to_response(readiness),
        application=app,
        active_session=_session_to_response(active_session) if active_session else None,
        listing_url_exact=exact,
        fallback_link=fallback_link,
        fallback_is_search=fallback_is_search,
    )


@router.post("/{job_id}/launch-application", response_model=LaunchApplicationResponse)
async def launch_application(
    job_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> LaunchApplicationResponse:
    """Creates the Application record if one doesn't exist yet (same
    idempotent pattern as save_job/apply_to_job), then either resumes the
    existing in-progress session or starts a new one. Returns the job URL
    for the frontend to open — Launch never navigates or submits anything
    server-side."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    app = session.exec(select(Application).where(Application.job_id == job_id)).first()
    is_new_app = app is None
    if app is None:
        app = Application(job_id=job_id)
        session.add(app)
        session.flush()  # assigns app.id without ending the transaction

    active_resume = session.exec(select(Resume).where(Resume.is_active == True)).first()  # noqa: E712
    profile = session.exec(select(ApplicationProfile)).first()

    existing_session = get_active_session(session, app.id)
    if existing_session:
        existing_session.last_opened_at = datetime.utcnow()
        session.add(existing_session)
        log_application_event(session, app.id, "session_resumed", detail="Application resumed")
        the_session = existing_session
    else:
        the_session = ApplicationSession(
            application_id=app.id,
            resume_version=active_resume.filename if active_resume else None,
            cover_letter_version=(
                job.cover_letter_generated_at.isoformat() if job.cover_letter_generated_at else None
            ),
            profile_version=profile.updated_at.isoformat() if profile else None,
        )
        session.add(the_session)
        log_application_event(session, app.id, "session_started", detail="Application started")

    if is_new_app:
        log_application_event(session, app.id, "created", to_status=app.status)

    session.commit()
    session.refresh(app)
    session.refresh(the_session)

    if is_new_app:
        _dispatch_application_created(background_tasks, job, app)

    return LaunchApplicationResponse(
        url=job.url,
        application=app,
        session=_session_to_response(the_session),
    )


_VALID_OUTCOMES = {"applied", "not_yet", "cancelled", "listing_unavailable"}


@router.post("/{job_id}/application-session/complete", response_model=CompleteSessionResponse)
async def complete_application_session(
    job_id: int,
    body: CompleteSessionRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> CompleteSessionResponse:
    """Manual completion — Kiwi never guesses whether an application was
    actually submitted. The user tells it: Applied, Not Yet, Cancelled, or
    Listing Unavailable (the third-party listing turned out to be expired
    or removed — Kiwi can't detect this itself, only the user can)."""
    if body.outcome not in _VALID_OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {sorted(_VALID_OUTCOMES)}")

    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    app = session.exec(select(Application).where(Application.job_id == job_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="No application exists for this job yet")

    the_session = get_active_session(session, app.id)
    if not the_session:
        raise HTTPException(status_code=409, detail="No in-progress application session for this job")

    if body.outcome == "applied":
        the_session.status = ApplicationSessionStatus.COMPLETED
        the_session.completed_at = datetime.utcnow()
        session.add(the_session)
        log_application_event(session, app.id, "session_completed", detail="Applied")

        previous_status = app.status
        status_changed = previous_status != ApplicationStatus.APPLIED
        app.status = ApplicationStatus.APPLIED
        if app.applied_at is None:
            app.applied_at = datetime.utcnow()
        app.updated_at = datetime.utcnow()
        session.add(app)
        if status_changed:
            log_application_event(
                session, app.id, "status_change", from_status=previous_status, to_status=app.status
            )
        session.commit()
        session.refresh(app)
        session.refresh(the_session)
        if status_changed:
            _dispatch_application_status_changed(background_tasks, job, app, previous_status)

    elif body.outcome == "cancelled":
        the_session.status = ApplicationSessionStatus.CANCELLED
        the_session.completed_at = datetime.utcnow()
        session.add(the_session)
        log_application_event(session, app.id, "session_cancelled", detail="Application cancelled")
        session.commit()
        session.refresh(app)
        session.refresh(the_session)

    elif body.outcome == "listing_unavailable":
        the_session.status = ApplicationSessionStatus.CANCELLED
        the_session.completed_at = datetime.utcnow()
        session.add(the_session)

        previous_status = app.status
        app.status = ApplicationStatus.UNAVAILABLE
        app.updated_at = datetime.utcnow()
        session.add(app)
        log_application_event(
            session, app.id, "session_listing_unavailable",
            from_status=previous_status, to_status=app.status,
            detail="Listing reported unavailable/expired",
        )
        session.commit()
        session.refresh(app)
        session.refresh(the_session)

    else:  # "not_yet" — still in progress server-side, nothing to change
        pass

    return CompleteSessionResponse(application=app, session=_session_to_response(the_session))


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
    had_summary = bool(job.summary_json)
    summary = load_job_summary(job)
    if not had_summary:
        session.add(job)  # load_job_summary generated one on the fly — persist it
        session.commit()

    if not summary.is_empty():
        # The Prompt Engine consumes the structured Kiwi Job Summary
        # whenever one exists — it's what the AI Workspace itself shows the
        # user, so the prompt matches what they saw.
        job_description_text = render_summary_as_text(summary)
    elif job.description:
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
        # Job Intelligence (Phase 9) — grounds the "Why am I a good fit?"
        # prompt in Kiwi's own deterministic reasons rather than letting the
        # AI guess; unused by every other template.
        "match_reasons": "\n".join(f"- {r}" for r in evaluate_job_intelligence(job, summary).reasons),
    }

    content = render_template(action.template_file, variables)

    if action_id == "cover_letter":
        # Kiwi never stores the AI's actual output (it's pasted into Claude
        # by hand) — this timestamp is the only signal the Application
        # Readiness Engine can use for "a cover letter has been prepared."
        job.cover_letter_generated_at = datetime.utcnow()
        session.add(job)
        session.commit()

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
