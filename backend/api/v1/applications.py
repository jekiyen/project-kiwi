from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from backend.database.models import (
    Application,
    ApplicationStatus,
    ApplicationUpdate,
    ApplicationWithJob,
    Job,
    PipelineCounts,
)
from backend.database.session import get_session

router = APIRouter(prefix="/applications", tags=["applications"])


def _build_with_job(app: Application, job: Job) -> ApplicationWithJob:
    return ApplicationWithJob(
        id=app.id,
        job_id=app.job_id,
        status=app.status,
        notes=app.notes,
        applied_at=app.applied_at,
        interview_date=app.interview_date,
        follow_up_date=app.follow_up_date,
        created_at=app.created_at,
        updated_at=app.updated_at,
        job_title=job.title,
        job_employer=job.employer,
        job_location=job.location,
        job_url=job.url,
        job_source=job.source,
        job_ai_match_score=job.ai_match_score,
        job_role_priority=job.role_priority.value if job.role_priority else None,
        job_ai_priority=job.ai_priority,
        job_salary_text=job.salary_text,
    )


# ── Pipeline counts — registered before /{id} to avoid route conflict ─────────

@router.get("/pipeline", response_model=PipelineCounts)
async def get_pipeline(session: Session = Depends(get_session)) -> PipelineCounts:
    """Return count of applications at each pipeline stage."""
    rows = session.execute(
        sa.select(Application.status, sa.func.count().label("n"))
        .group_by(Application.status)
    ).all()
    # row[0] is ApplicationStatus enum member; .value gives the lowercase string
    counts: dict[str, int] = {row[0].value: row[1] for row in rows}
    total = sum(counts.values())
    return PipelineCounts(
        saved=counts.get("saved", 0),
        applied=counts.get("applied", 0),
        interview=counts.get("interview", 0),
        offer=counts.get("offer", 0),
        rejected=counts.get("rejected", 0),
        visa=counts.get("visa", 0),
        archived=counts.get("archived", 0),
        total=total,
    )


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("/")
async def list_applications(
    session: Session = Depends(get_session),
    status: Optional[str] = Query(None, description="Filter by status value"),
    search: Optional[str] = Query(None, description="Search by job title or employer"),
) -> list[ApplicationWithJob]:
    """List all applications, joined with job details. Sorted by most recently updated."""
    stmt = (
        sa.select(Application, Job)
        .join(Job, Application.job_id == Job.id)
        .order_by(Application.updated_at.desc())
    )
    if status:
        stmt = stmt.where(Application.status == status)
    if search:
        term = f"%{search.lower()}%"
        stmt = stmt.where(
            sa.or_(
                sa.func.lower(Job.title).like(term),
                sa.func.lower(Job.employer).like(term),
            )
        )
    rows = session.execute(stmt).all()
    return [_build_with_job(app, job) for app, job in rows]


@router.post("/", status_code=201)
async def create_application(
    job_id: int,
    status: ApplicationStatus = ApplicationStatus.SAVED,
    notes: Optional[str] = None,
    session: Session = Depends(get_session),
) -> Application:
    """Create a new application record for a job."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    existing = session.exec(
        select(Application).where(Application.job_id == job_id)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Application already exists for this job")
    app = Application(
        job_id=job_id,
        status=status,
        notes=notes,
        applied_at=datetime.utcnow() if status == ApplicationStatus.APPLIED else None,
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


@router.patch("/{application_id}")
async def update_application(
    application_id: int,
    body: ApplicationUpdate,
    session: Session = Depends(get_session),
) -> Application:
    """Update status, notes, or date fields on an existing application."""
    app = session.get(Application, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if body.status is not None:
        # Auto-set applied_at the first time status moves to APPLIED
        if body.status == ApplicationStatus.APPLIED and app.applied_at is None:
            app.applied_at = datetime.utcnow()
        app.status = body.status
    if body.notes is not None:
        app.notes = body.notes
    if body.applied_at is not None:
        app.applied_at = body.applied_at
    if body.interview_date is not None:
        app.interview_date = body.interview_date
    if body.follow_up_date is not None:
        app.follow_up_date = body.follow_up_date

    app.updated_at = datetime.utcnow()
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


@router.delete("/{application_id}", status_code=204)
async def delete_application(
    application_id: int,
    session: Session = Depends(get_session),
) -> None:
    """Remove an application record."""
    app = session.get(Application, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    session.delete(app)
    session.commit()
