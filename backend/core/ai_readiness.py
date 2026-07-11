"""Evaluates whether a job has enough data for good AI output.

This is the single source of truth for "AI Readiness" — used both by the
AI Workspace's readiness card (GET /jobs/{id}/ai-readiness) and by the
Prompt Guard inside GET /jobs/{id}/prompts/{action_id}, so the UI and the
guard that blocks generation can never disagree. See docs/ROADMAP.md
Phase 7.5.
"""
from dataclasses import dataclass
from enum import Enum

from backend.database.models import Job, Resume


class ReadinessStatus(str, Enum):
    READY = "ready"
    PARTIAL = "partial"
    NOT_READY = "not_ready"


@dataclass(frozen=True)
class AIReadiness:
    status: ReadinessStatus
    missing: list[str]
    impact: str


_NOT_READY_IMPACT = (
    "AI generation is disabled until the missing information above is added — "
    "without it Kiwi can't produce a meaningful prompt."
)
_PARTIAL_IMPACT = (
    "AI analysis will be based only on the job title and company. ATS analysis, "
    "Cover Letter, and Interview Preparation will be less accurate."
)
_READY_IMPACT = "All required job details and an active resume are present."


def evaluate_ai_readiness(job: Job, active_resume: Resume | None) -> AIReadiness:
    """Hard requirements (Job Title, Company, Active Resume) block generation
    entirely when missing — Not Ready. Soft requirements (Job Description)
    degrade quality but don't block it — Partial."""
    missing_hard: list[str] = []
    if not job.title:
        missing_hard.append("Job Title")
    if not job.employer:
        missing_hard.append("Company")
    if active_resume is None:
        missing_hard.append("Active Resume")

    if missing_hard:
        return AIReadiness(status=ReadinessStatus.NOT_READY, missing=missing_hard, impact=_NOT_READY_IMPACT)

    missing_soft: list[str] = []
    if not job.description:
        missing_soft.append("Job Description")

    if missing_soft:
        return AIReadiness(status=ReadinessStatus.PARTIAL, missing=missing_soft, impact=_PARTIAL_IMPACT)

    return AIReadiness(status=ReadinessStatus.READY, missing=[], impact=_READY_IMPACT)
