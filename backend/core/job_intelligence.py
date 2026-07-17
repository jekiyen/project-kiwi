"""Job Intelligence — deterministic scoring, recommendation, and gap
analysis for job listings. See docs/ROADMAP.md Phase 9.

This is an interpretation layer, not a second scorer: it never re-derives a
score from raw text. The actual deterministic scoring already happens in
`ManualProvider` (backend/ai/manual.py, keyword-based, no API calls) and is
stored on `Job.ai_match_score` / `ai_confidence` / `ai_reasons` once a job has
been analysed. Job Intelligence reads those existing fields — plus the
Phase 7.6 Kiwi Job Summary and Job's own visa_* flags — and turns them into a
Recommendation Badge, a plain-language reason list, and a list of what the
listing itself didn't specify. For a job that hasn't been analysed yet, it
falls back to `backend/core/matcher.py`'s structured-fields-only score
(the same one Phase 2/3 already used) rather than inventing a new formula.

Never calls an AI provider. Never invents a missing value — gaps are always
reported as "<field>: Not specified," never guessed.
"""
import json
import re
from dataclasses import dataclass
from enum import Enum

from backend.core import matcher
from backend.database.models import Job
from backend.job_summary import JobSummary


class RecommendationLevel(str, Enum):
    HIGHLY_RECOMMENDED = "highly_recommended"
    RECOMMENDED = "recommended"
    CONSIDER = "consider"
    LOW_PRIORITY = "low_priority"


# Ordered highest-first — the first threshold met wins.
_THRESHOLDS: list[tuple[int, RecommendationLevel]] = [
    (80, RecommendationLevel.HIGHLY_RECOMMENDED),
    (60, RecommendationLevel.RECOMMENDED),
    (35, RecommendationLevel.CONSIDER),
]

# A job that hasn't gone through analyse yet only has the structured-fields
# fallback score (backend/core/matcher.py) behind it — lower confidence than
# a job ManualProvider has actually scored from its full text.
_UNSCORED_FALLBACK_CONFIDENCE = 40


def recommendation_for_score(score: int) -> RecommendationLevel:
    for threshold, level in _THRESHOLDS:
        if score >= threshold:
            return level
    return RecommendationLevel.LOW_PRIORITY


@dataclass(frozen=True)
class JobIntelligence:
    score: int
    confidence: int
    recommendation: RecommendationLevel
    reasons: list[str]
    missing_requirements: list[str]


def _fallback_reasons(job: Job) -> list[str]:
    """Used only when Job.ai_reasons isn't populated yet (job never
    analysed) — built from structured fields already on the row, never from
    re-scanning raw text a second time."""
    reasons: list[str] = []
    if job.role_priority:
        reasons.append(f"Role priority: {job.role_priority.value}.")
    else:
        reasons.append("Role does not clearly match your target P1-P3 categories.")
    if job.visa_accredited_employer:
        reasons.append("Employer appears to be accredited for visa sponsorship.")
    if job.visa_overseas_friendly:
        reasons.append("Listing signals it's open to overseas applicants.")
    if job.visa_sponsorship_potential:
        reasons.append("Visa sponsorship is mentioned.")
    if job.visa_nz_rights_required:
        reasons.append("Listing appears to require existing NZ work rights.")
    reasons.append("This job hasn't been analysed yet — run AI analysis for a fuller explanation.")
    return reasons


def _reasons_for(job: Job) -> list[str]:
    """Prefer the reasons ManualProvider already computed and stored on the
    job — never re-derive a second, possibly-inconsistent explanation."""
    if job.ai_reasons:
        try:
            parsed = json.loads(job.ai_reasons)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, list) and parsed:
            return [str(r) for r in parsed]
    return _fallback_reasons(job)


def _missing_requirements(job: Job, summary: JobSummary) -> list[str]:
    """What THIS listing itself didn't specify — never a comparison against
    the applicant's own qualifications, purely gaps in the source posting."""
    missing: list[str] = []
    if not summary.requirements_required and not summary.requirements_preferred:
        missing.append("Requirements: Not specified")
    if not job.salary_text:
        missing.append("Salary: Not specified")
    # No job source Kiwi scrapes provides a structured employment-type field.
    missing.append("Employment Type: Not specified")
    if not job.description:
        missing.append("Job Description: Not specified")
    if not any([
        job.visa_accredited_employer,
        job.visa_overseas_friendly,
        job.visa_sponsorship_potential,
        job.visa_nz_rights_required,
    ]):
        missing.append("Visa / Work Rights Policy: Not specified")
    return missing


def evaluate_job_intelligence(job: Job, summary: JobSummary) -> JobIntelligence:
    if job.ai_match_score is not None:
        score = round(job.ai_match_score)
        confidence = job.ai_confidence if job.ai_confidence is not None else 80
    else:
        score = round(matcher.score_job(job) * 100)
        confidence = _UNSCORED_FALLBACK_CONFIDENCE

    return JobIntelligence(
        score=score,
        confidence=confidence,
        recommendation=recommendation_for_score(score),
        reasons=_reasons_for(job),
        missing_requirements=_missing_requirements(job, summary),
    )


# ── Similar Jobs ──────────────────────────────────────────────────────────────

_STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "at", "on", "with",
    "wanted", "needed", "required", "urgent", "immediate", "start",
}


def _title_tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", title.lower()) if w not in _STOPWORDS and len(w) > 2}


@dataclass(frozen=True)
class SimilarJob:
    job: Job
    similarity_score: int


def find_similar_jobs(job: Job, candidates: list[Job], limit: int = 5) -> list[SimilarJob]:
    """Deterministic similarity using Title (token overlap), Industry
    (role_priority — the closest proxy Kiwi has, since no job source
    provides a real industry field), and Location. Employment Type is
    intentionally skipped: no job source provides it, so comparing it would
    always trivially "match" without meaning anything."""
    target_tokens = _title_tokens(job.title)
    target_location = job.location.strip().lower()

    scored: list[SimilarJob] = []
    for candidate in candidates:
        if candidate.id == job.id:
            continue
        points = 0
        if job.role_priority is not None and candidate.role_priority == job.role_priority:
            points += 3
        if target_location and candidate.location.strip().lower() == target_location:
            points += 3
        shared = target_tokens & _title_tokens(candidate.title)
        points += min(len(shared) * 2, 4)
        if points > 0:
            scored.append(SimilarJob(job=candidate, similarity_score=points))

    scored.sort(key=lambda s: (-s.similarity_score, -(s.job.ai_match_score or 0)))
    return scored[:limit]
