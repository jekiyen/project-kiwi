from typing import Optional

from sqlmodel import Session, select

from backend.database.models import ApplicationEvent, ApplicationStatus, Job, Scan, ScraperRun


def get_job_by_external_id(session: Session, external_id: str, source: str) -> Job | None:
    return session.exec(
        select(Job).where(Job.external_id == external_id, Job.source == source)
    ).first()


def get_recent_scans(session: Session, limit: int = 50) -> list[Scan]:
    return list(
        session.exec(select(Scan).order_by(Scan.started_at.desc()).limit(limit)).all()
    )


def get_active_jobs(session: Session, limit: int = 100, offset: int = 0) -> list[Job]:
    return list(
        session.exec(
            select(Job)
            .where(Job.is_active == True)  # noqa: E712
            .order_by(Job.ai_match_score.desc(), Job.first_seen_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


def log_application_event(
    session: Session,
    application_id: int,
    event_type: str,
    from_status: Optional[ApplicationStatus] = None,
    to_status: Optional[ApplicationStatus] = None,
    detail: Optional[str] = None,
) -> ApplicationEvent:
    """Record a timeline entry for an application. Caller is responsible for commit."""
    event = ApplicationEvent(
        application_id=application_id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        detail=detail,
    )
    session.add(event)
    return event


def get_application_timeline(session: Session, application_id: int) -> list[ApplicationEvent]:
    return list(
        session.exec(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application_id)
            .order_by(ApplicationEvent.created_at.asc())
        ).all()
    )
