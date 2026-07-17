"""Application Readiness — the single evaluator for "is the user ready to
apply to this job." Distinct from AI Readiness (backend/core/ai_readiness.py,
which asks "is there enough job data for a good AI prompt"): this evaluator
asks "does the applicant have everything Kiwi can check for before they open
the employer's site" — active resume, a filled-in Application Profile, a
generated cover letter for this job, at least one reference, and the Work
Rights section of the profile.

Used by the Application Kit (GET /jobs/{id}/application-kit), the Dashboard's
bulk badge (GET /jobs/readiness-summary), and nowhere else duplicates these
rules — see docs/ROADMAP.md Phase 8.
"""
from dataclasses import dataclass
from enum import Enum

from backend.database.models import ApplicationProfile, ApplicationReference, Job, Resume

# Rough, deterministic time estimate — not a promise, just a useful signal.
# Filling out the employer's own application form is the fixed cost; each
# missing item adds prep time before the applicant should even open it.
_BASE_MINUTES = 15
_MINUTES_PER_HARD_ITEM = 10
_MINUTES_PER_SOFT_ITEM = 5


class ApplicationReadinessStatus(str, Enum):
    READY = "ready"
    PARTIAL = "partial"
    NOT_READY = "not_ready"


@dataclass(frozen=True)
class SectionReadiness:
    resume: bool
    application_profile: bool
    cover_letter: bool
    references: bool
    work_rights: bool


@dataclass(frozen=True)
class ApplicationReadiness:
    status: ApplicationReadinessStatus
    sections: SectionReadiness
    missing: list[str]
    score: int  # 0-100
    estimated_minutes: int


def evaluate_application_readiness(
    job: Job,
    profile: ApplicationProfile | None,
    references: list[ApplicationReference],
    active_resume: Resume | None,
) -> ApplicationReadiness:
    """Hard requirements (Active Resume, a filled-in Application Profile)
    block launching entirely when missing — Not Ready. Soft requirements
    (Cover Letter, References, Work Rights, Phone Number, Driver License)
    degrade the score but don't block it — Partial."""
    resume_ok = active_resume is not None
    # A profile "exists" as a DB row from the moment it's first read (Phase
    # 8.0's lazy singleton) — that's not the same as the user having filled
    # anything in, so require at least one identifying field before it counts.
    profile_filled = bool(profile) and bool(profile.full_name or profile.email or profile.phone)
    cover_letter_ok = bool(job.cover_letter_generated_at)
    references_ok = len(references) > 0
    phone_ok = bool(profile) and bool(profile.phone)
    driver_license_ok = bool(profile) and bool(profile.driver_license)
    work_rights_ok = bool(profile) and bool(profile.visa_status or profile.work_rights_current_country)

    missing: list[str] = []
    missing_hard_count = 0
    missing_soft_count = 0

    if not resume_ok:
        missing.append("Resume")
        missing_hard_count += 1
    if not profile_filled:
        missing.append("Application Profile")
        missing_hard_count += 1

    if not cover_letter_ok:
        missing.append("Cover Letter")
        missing_soft_count += 1
    if not references_ok:
        missing.append("Reference")
        missing_soft_count += 1
    # These three only make sense to flag once there's a profile to check —
    # an entirely-missing profile already reported above covers them.
    if profile_filled and not phone_ok:
        missing.append("Phone Number")
        missing_soft_count += 1
    if profile_filled and not driver_license_ok:
        missing.append("Driver License")
        missing_soft_count += 1
    if profile_filled and not work_rights_ok:
        missing.append("Work Rights")
        missing_soft_count += 1

    if missing_hard_count:
        status = ApplicationReadinessStatus.NOT_READY
    elif missing_soft_count:
        status = ApplicationReadinessStatus.PARTIAL
    else:
        status = ApplicationReadinessStatus.READY

    checks = [resume_ok, profile_filled, cover_letter_ok, references_ok]
    if profile_filled:
        checks += [phone_ok, driver_license_ok, work_rights_ok]
    score = round(100 * sum(checks) / len(checks))

    estimated_minutes = (
        _BASE_MINUTES
        + _MINUTES_PER_HARD_ITEM * missing_hard_count
        + _MINUTES_PER_SOFT_ITEM * missing_soft_count
    )

    sections = SectionReadiness(
        resume=resume_ok,
        application_profile=profile_filled,
        cover_letter=cover_letter_ok,
        references=references_ok,
        work_rights=work_rights_ok,
    )

    return ApplicationReadiness(
        status=status,
        sections=sections,
        missing=missing,
        score=score,
        estimated_minutes=estimated_minutes,
    )
