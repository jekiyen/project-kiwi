from backend.database.models import Job


def tag_visa_eligibility(job: Job, description: str) -> Job:
    """
    Heuristically tag visa fields from job description text.
    Phase 3: replaced by AI-powered analysis via AIProvider.
    """
    text = description.lower()
    job.visa_accredited_employer = "accredited employer" in text
    job.visa_overseas_friendly = any(k in text for k in ["overseas", "international applicant", "relocation"])
    job.visa_nz_rights_required = any(k in text for k in ["must have nz", "nz residency", "nz citizen", "work visa not supported"])
    return job
