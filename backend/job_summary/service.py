"""Wires the deterministic extractor into the places a Job's description is
set or changed — scraper ingestion and the Edit Job fast path — so
summary_json always reflects the current raw description.
"""
from backend.database.models import Job
from backend.job_summary.extractor import generate_job_summary
from backend.job_summary.models import JobSummary


def summarize_job(job: Job) -> None:
    """Regenerate job.summary_json from job.description (+ job.salary_text).
    Never touches job.description — the raw text is always preserved."""
    summary = generate_job_summary(job.description, job.salary_text)
    job.summary_json = summary.model_dump_json()


def load_job_summary(job: Job) -> JobSummary:
    """Parse job.summary_json, generating it on the fly (write-through) for
    jobs created before Phase 7.6 that don't have one stored yet."""
    if not job.summary_json:
        summarize_job(job)
    return JobSummary.model_validate_json(job.summary_json)
