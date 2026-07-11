"""The "Kiwi Job Summary" — a structured, deterministic breakdown of a raw
job description. See docs/ROADMAP.md Phase 7.6.
"""
from pydantic import BaseModel, Field


class JobSummary(BaseModel):
    overview: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    requirements_required: list[str] = Field(default_factory=list)
    requirements_preferred: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    work_environment: list[str] = Field(default_factory=list)
    salary: str = ""
    visa_notes: str = ""
    warnings: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        """True when nothing at all could be extracted — warnings don't
        count as content. Used to decide whether the UI/Prompt Engine should
        fall back to the raw description instead."""
        return not any([
            self.overview,
            self.responsibilities,
            self.requirements_required,
            self.requirements_preferred,
            self.benefits,
            self.work_environment,
            self.salary,
            self.visa_notes,
        ])
