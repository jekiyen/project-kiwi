from fastapi import APIRouter, BackgroundTasks, Depends
from sqlmodel import Session, select

from backend.agents.scan_agent import ScanAgent
from backend.database.models import Scan, ScanDetail, ScraperRun
from backend.database.queries import get_recent_scans
from backend.database.session import get_session

router = APIRouter(prefix="/scans", tags=["scans"])


@router.get("/")
async def list_scans(session: Session = Depends(get_session)) -> list[ScanDetail]:
    scans = get_recent_scans(session)
    result: list[ScanDetail] = []

    for scan in scans:
        runs = list(
            session.exec(
                select(ScraperRun)
                .where(ScraperRun.scan_id == scan.id)
                .order_by(ScraperRun.started_at)
            ).all()
        )
        result.append(
            ScanDetail(
                id=scan.id,
                started_at=scan.started_at,
                completed_at=scan.completed_at,
                source=scan.source,
                jobs_found=scan.jobs_found,
                new_jobs=scan.new_jobs,
                changed_jobs=scan.changed_jobs,
                errors=scan.errors,
                status=scan.status,
                total_duplicates=scan.total_duplicates,
                total_errors=scan.total_errors,
                duration_ms=scan.duration_ms,
                scraper_runs=runs,
            )
        )

    return result


@router.post("/trigger")
async def trigger_scan(background_tasks: BackgroundTasks) -> dict:
    agent = ScanAgent()
    background_tasks.add_task(agent.run)
    return {"message": "Scan triggered successfully"}
