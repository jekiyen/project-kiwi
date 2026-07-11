"""Renders a JobSummary back into plain text for the Prompt Engine. Prompts
are copied verbatim into Claude by a human, so this stays plain and
readable rather than JSON.
"""
from backend.job_summary.models import JobSummary


def render_summary_as_text(summary: JobSummary) -> str:
    parts: list[str] = []

    if summary.overview:
        parts.append(summary.overview)
    if summary.responsibilities:
        parts.append("Responsibilities:\n" + "\n".join(f"- {r}" for r in summary.responsibilities))
    if summary.requirements_required:
        parts.append("Requirements:\n" + "\n".join(f"- {r}" for r in summary.requirements_required))
    if summary.requirements_preferred:
        parts.append("Preferred:\n" + "\n".join(f"- {r}" for r in summary.requirements_preferred))
    if summary.benefits:
        parts.append("Benefits:\n" + "\n".join(f"- {b}" for b in summary.benefits))
    if summary.work_environment:
        parts.append("Work Environment:\n" + "\n".join(f"- {w}" for w in summary.work_environment))
    if summary.salary:
        parts.append(f"Salary: {summary.salary}")
    if summary.visa_notes:
        parts.append(f"Visa Notes: {summary.visa_notes}")

    return "\n\n".join(parts)
