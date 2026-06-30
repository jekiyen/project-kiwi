import json
import logging
import time
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from backend.agents.base import AgentResult, BaseAgent
from backend.config.settings import settings
from backend.config.user_profile import USER_PROFILE
from backend.core.deduplication import find_changes, is_duplicate
from backend.core.matcher import classify_role
from backend.database.models import Job, JobChange, Scan, ScanStatus, ScraperRun
from backend.database.queries import get_job_by_external_id
from backend.database.session import engine
from backend.scrapers.base import ScrapedJob

logger = logging.getLogger("scanner")


class ScanAgent(BaseAgent):
    name = "scan_agent"
    description = "Scrapes all job platforms, analyses results, and triggers notifications."

    @property
    def schedule_interval_hours(self) -> int:
        return settings.scan_interval_hours

    async def run(self) -> AgentResult:
        logger.info("Scan started")
        scan_start = time.monotonic()

        with Session(engine) as session:
            scan = Scan(source="all", status=ScanStatus.RUNNING)
            session.add(scan)
            session.commit()
            session.refresh(scan)
            scan_id = scan.id

        all_scraped, scraper_runs = await self._run_scrapers(scan_id)

        # Aggregate across all scraper runs
        total_found = sum(r.jobs_found for r in scraper_runs)
        total_inserted = sum(r.jobs_inserted for r in scraper_runs)
        total_dupes = sum(r.duplicates_skipped for r in scraper_runs)
        total_errors = sum(1 for r in scraper_runs if r.status == "failed")
        changed_jobs = sum(r.jobs_found - r.jobs_inserted - r.duplicates_skipped
                          for r in scraper_runs if r.status != "failed")
        changed_jobs = max(changed_jobs, 0)

        analyzed = await self._analyze_pending(scan_id)

        scan_duration_ms = int((time.monotonic() - scan_start) * 1000)

        with Session(engine) as session:
            scan = session.get(Scan, scan_id)
            scan.jobs_found = total_found
            scan.new_jobs = total_inserted
            scan.changed_jobs = changed_jobs
            scan.total_duplicates = total_dupes
            scan.total_errors = total_errors
            scan.duration_ms = scan_duration_ms
            scan.completed_at = datetime.utcnow()
            scan.status = ScanStatus.FAILED if total_errors == len(scraper_runs) else ScanStatus.COMPLETED
            session.add(scan)
            session.commit()

        logger.info(
            "Scan complete — found=%d new=%d dupes=%d errors=%d analyzed=%d duration=%dms",
            total_found, total_inserted, total_dupes, total_errors, analyzed, scan_duration_ms,
        )
        return AgentResult(
            success=True,
            message=f"Scan complete: {total_inserted} new job(s), {analyzed} scored.",
            data={
                "found": total_found,
                "new_jobs": total_inserted,
                "duplicates": total_dupes,
                "scraper_errors": total_errors,
                "analyzed": analyzed,
            },
        )

    async def _run_scrapers(self, scan_id: int) -> tuple[list[ScrapedJob], list[ScraperRun]]:
        from backend.scrapers.seek import SeekScraper
        from backend.scrapers.trademe import TradeMeScraper
        from backend.scrapers.picknz import PickNZScraper
        from backend.scrapers.backpacker import BackpackerBoardScraper
        from backend.scrapers.seasonal import SeasonalJobsScraper
        from backend.scrapers.indeed import IndeedScraper

        scrapers = [
            SeekScraper(),
            TradeMeScraper(),
            PickNZScraper(),
            BackpackerBoardScraper(),
            SeasonalJobsScraper(),
            IndeedScraper(),
        ]

        all_scraped: list[ScrapedJob] = []
        runs: list[ScraperRun] = []

        for scraper in scrapers:
            scraper_start = time.monotonic()
            started_at = datetime.utcnow()
            jobs: list[ScrapedJob] = []
            error_msg: Optional[str] = None

            try:
                logger.info("Running scraper: %s", scraper.source_name)
                jobs = await scraper.scrape()
            except Exception as exc:
                error_msg = str(exc)
                logger.error("Scraper '%s' failed: %s", scraper.source_name, exc)

            duration_ms = int((time.monotonic() - scraper_start) * 1000)

            # Store jobs for this scraper and collect per-source counts
            inserted = 0
            dupes = 0
            if jobs:
                with Session(engine) as session:
                    inserted, _, dupes = self._store_scraped_jobs(session, jobs)

            # Determine scraper status
            if error_msg:
                status = "failed"
            elif len(jobs) == 0:
                status = "partial"
            else:
                status = "success"

            run = ScraperRun(
                scan_id=scan_id,
                source=scraper.source_name,
                status=status,
                jobs_found=len(jobs),
                jobs_inserted=inserted,
                duplicates_skipped=dupes,
                errors=error_msg,
                duration_ms=duration_ms,
                started_at=started_at,
                finished_at=datetime.utcnow(),
            )

            with Session(engine) as session:
                session.add(run)
                session.commit()
                session.refresh(run)

            runs.append(run)
            all_scraped.extend(jobs)

            logger.info(
                "Scraper '%s' → status=%s found=%d inserted=%d dupes=%d duration=%dms",
                scraper.source_name, status, len(jobs), inserted, dupes, duration_ms,
            )

        return all_scraped, runs

    def _store_scraped_jobs(
        self, session: Session, scraped_jobs: list[ScrapedJob]
    ) -> tuple[int, int, int]:
        """Store scraped jobs. Returns (new_count, changed_count, dupe_count)."""
        new_count = 0
        changed_count = 0
        dupe_count = 0

        for scraped in scraped_jobs:
            if is_duplicate(session, scraped.external_id, scraped.source):
                dupe_count += 1
                existing = get_job_by_external_id(session, scraped.external_id, scraped.source)
                if existing:
                    changes = find_changes(existing, {
                        "title": scraped.title,
                        "salary_text": scraped.salary_text,
                        "description": scraped.description,
                    })
                    if changes:
                        for field, (old_val, new_val) in changes.items():
                            session.add(JobChange(
                                job_id=existing.id,
                                field_changed=field,
                                old_value=old_val,
                                new_value=new_val,
                            ))
                        existing.last_seen_at = datetime.utcnow()
                        session.add(existing)
                        changed_count += 1
            else:
                job = Job(
                    external_id=scraped.external_id,
                    source=scraped.source,
                    title=scraped.title,
                    employer=scraped.employer,
                    location=scraped.location,
                    url=scraped.url,
                    description=scraped.description,
                    salary_text=scraped.salary_text,
                    role_priority=classify_role(scraped.title, scraped.description or ""),
                    raw_data=json.dumps(scraped.raw_data) if scraped.raw_data else None,
                )
                session.add(job)
                new_count += 1

        session.commit()
        return new_count, changed_count, dupe_count

    async def _analyze_pending(self, scan_id: int, force: bool = False) -> int:
        """Score all unanalysed jobs. Returns count scored."""
        from backend.ai import get_ai_provider

        provider = get_ai_provider()

        with Session(engine) as session:
            stmt = select(Job)
            if not force:
                stmt = stmt.where(Job.ai_analysed_at == None)  # noqa: E711
            jobs = list(session.exec(stmt).all())

        if not jobs:
            return 0

        logger.info(
            "Analyzing %d job(s) with %s (force=%s)",
            len(jobs), provider.__class__.__name__, force,
        )

        results: list[tuple[int, object]] = []
        for job in jobs:
            job_data = {
                "title": job.title,
                "employer": job.employer,
                "location": job.location,
                "description": job.description or "",
                "salary_text": job.salary_text or "",
            }
            analysis = await provider.analyze_job(job_data, USER_PROFILE)
            results.append((job.id, analysis))

        with Session(engine) as session:
            for job_id, analysis in results:
                job = session.get(Job, job_id)
                if not job:
                    continue
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

        logger.info("Analysis complete — %d job(s) scored", len(results))
        return len(results)
