from sqlmodel import Session, select

from backend.database.models import Job, Scan, ScraperRun


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
