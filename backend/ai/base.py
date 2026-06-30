from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class JobAnalysis:
    # ── Core scoring ──────────────────────────────────────────────────────────
    score: int                          # 0–100
    priority: str                       # "P1" | "P2" | "P3" | "Reject"
    explanation: str                    # single-sentence summary for display
    reasons: list[str] = field(default_factory=list)   # structured reason list
    pros: list[str]    = field(default_factory=list)
    cons: list[str]    = field(default_factory=list)

    # ── Visa signals ──────────────────────────────────────────────────────────
    visa_accredited_employer: bool = False
    visa_overseas_friendly: bool   = False
    visa_sponsorship_potential: bool = False
    visa_nz_rights_required: bool  = False
    visa_probability: int = 0           # 0–100 estimated chance of obtaining work visa

    # ── Meta ─────────────────────────────────────────────────────────────────
    confidence: int = 0                 # 0–100 provider confidence in the assessment
    provider: str   = ""                # "manual" | "claude" | ...
    model: str      = ""                # model identifier; empty for rule-based providers


class AIProvider(ABC):
    @abstractmethod
    async def analyze_job(self, job_data: dict, user_profile: dict) -> JobAnalysis:
        """Analyse a single job against the user profile and return a scored result."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if the provider is configured and reachable."""
        ...
