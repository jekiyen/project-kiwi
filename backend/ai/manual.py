from backend.ai.base import AIProvider, JobAnalysis
from backend.database.models import RolePriority

# ── Role keyword sets ─────────────────────────────────────────────────────────

_P1 = {
    "packhouse", "pack house", "packing", "picker", "picking", "fruit pick",
    "orchard", "farm worker", "farmhand", "farm hand", "seasonal worker",
    "crop pick", "harvest", "horticulture worker", "kiwifruit", "apple pick",
}
_P2 = {
    "warehouse", "manufacturing", "factory worker", "production worker",
    "production line", "assembly worker", "forklift", "dispatch worker",
    "stores person", "storeperson",
}
_P3 = {
    "labourer", "laborer", "general labour", "general labor",
    "construction labourer", "building labourer", "groundswork", "site labourer",
    "labour hire", "labor hire",
}

# ── Visa keyword sets ─────────────────────────────────────────────────────────

_ACCREDITED = {"accredited employer", "accredited immigration"}
_OVERSEAS = {
    "overseas applicant", "overseas candidates", "open to overseas",
    "international applicant", "relocation", "relocate to nz",
}
_SPONSORSHIP = {
    "work visa", "visa support", "visa sponsorship", "sponsorship available",
    "support visa", "help with visa",
}
_NZ_RIGHTS = {
    "must be a nz", "nz resident", "nz citizen", "new zealand citizen",
    "must have nz work rights", "eligible to work in nz without",
    "nz permanent resident", "right to work in nz", "must hold nz",
}

# ── Base scores per priority ──────────────────────────────────────────────────

_BASE: dict[RolePriority | None, int] = {
    RolePriority.P1: 70,
    RolePriority.P2: 55,
    RolePriority.P3: 40,
    None: 20,
}

_PRIORITY_LABEL: dict[RolePriority | None, str] = {
    RolePriority.P1: "P1",
    RolePriority.P2: "P2",
    RolePriority.P3: "P3",
    None: "Reject",
}

_ROLE_DESC: dict[RolePriority | None, str] = {
    RolePriority.P1: "Priority 1 role (packhouse / orchard / farm / picking) — direct match for your primary target category.",
    RolePriority.P2: "Priority 2 role (warehouse / factory / manufacturing) — secondary target category.",
    RolePriority.P3: "Priority 3 role (labourer / construction) — lower-priority target category.",
    None: "Role does not clearly align with your P1–P3 target categories.",
}


def _match_any(text: str, keywords: set[str]) -> bool:
    return any(k in text for k in keywords)


class ManualProvider(AIProvider):
    """
    Deterministic keyword-based scorer. No API calls.
    Returns consistent scores for the same job data every time.
    Used for development and testing before a real AI provider is enabled.
    """

    async def analyze_job(self, job_data: dict, user_profile: dict) -> JobAnalysis:
        text = " ".join(
            str(job_data.get(f, ""))
            for f in ("title", "description", "employer", "salary_text")
        ).lower()

        priority = self._detect_priority(text)
        visa = self._detect_visa(text)
        score = self._compute_score(priority, visa)
        reasons, pros, cons = self._build_lists(priority, visa)
        explanation = self._build_explanation(score, reasons)
        visa_prob = self._compute_visa_probability(priority, visa)

        return JobAnalysis(
            score=score,
            priority=_PRIORITY_LABEL[priority],
            explanation=explanation,
            reasons=reasons,
            pros=pros,
            cons=cons,
            visa_accredited_employer=visa["accredited"],
            visa_overseas_friendly=visa["overseas"],
            visa_sponsorship_potential=visa["sponsorship"],
            visa_nz_rights_required=visa["nz_rights"],
            visa_probability=visa_prob,
            confidence=80,
            provider="manual",
            model="",
        )

    async def is_available(self) -> bool:
        return True

    # ── Private helpers ───────────────────────────────────────────────────────

    def _detect_priority(self, text: str) -> RolePriority | None:
        if _match_any(text, _P1):
            return RolePriority.P1
        if _match_any(text, _P2):
            return RolePriority.P2
        if _match_any(text, _P3):
            return RolePriority.P3
        return None

    def _detect_visa(self, text: str) -> dict[str, bool]:
        return {
            "accredited": _match_any(text, _ACCREDITED),
            "overseas": _match_any(text, _OVERSEAS),
            "sponsorship": _match_any(text, _SPONSORSHIP),
            "nz_rights": _match_any(text, _NZ_RIGHTS),
        }

    def _compute_score(self, priority: RolePriority | None, visa: dict[str, bool]) -> int:
        score = _BASE[priority]
        if visa["accredited"]:
            score += 10
        if visa["overseas"]:
            score += 8
        if visa["sponsorship"]:
            score += 5
        if visa["nz_rights"]:
            score -= 25
        return max(0, min(100, score))

    def _compute_visa_probability(
        self, priority: RolePriority | None, visa: dict[str, bool]
    ) -> int:
        prob = 25  # Indonesian, no current NZ work rights
        if visa["accredited"]:
            prob += 30  # accredited employers can sponsor
        if visa["overseas"]:
            prob += 15  # explicitly open to overseas applicants
        if visa["sponsorship"]:
            prob += 20  # explicit sponsorship mentioned
        if visa["nz_rights"]:
            prob -= 50  # hard barrier: requires rights you don't have
        return max(0, min(100, prob))

    def _build_lists(
        self,
        priority: RolePriority | None,
        visa: dict[str, bool],
    ) -> tuple[list[str], list[str], list[str]]:
        reasons: list[str] = [_ROLE_DESC[priority]]
        pros: list[str] = []
        cons: list[str] = []

        if priority in (RolePriority.P1, RolePriority.P2, RolePriority.P3):
            pros.append(_ROLE_DESC[priority])
        else:
            cons.append("Role does not match your target job categories.")

        if visa["accredited"]:
            msg = "Employer appears to be accredited — strong positive for future visa sponsorship."
            reasons.append(msg)
            pros.append(msg)
        if visa["overseas"]:
            msg = "Listing signals it is open to overseas applicants."
            reasons.append(msg)
            pros.append(msg)
        if visa["sponsorship"]:
            msg = "Work visa support or sponsorship is mentioned."
            reasons.append(msg)
            pros.append(msg)
        if visa["nz_rights"]:
            msg = "Listing appears to require existing NZ work rights — significant barrier given your current visa situation."
            reasons.append(msg)
            cons.append(msg)

        if not any(visa.values()):
            reasons.append("No explicit visa eligibility signals detected — confirm directly with the employer.")

        return reasons, pros, cons

    def _build_explanation(self, score: int, reasons: list[str]) -> str:
        if score >= 70:
            verdict = f"Strong match ({score}/100)."
        elif score >= 40:
            verdict = f"Moderate match ({score}/100)."
        else:
            verdict = f"Weak match ({score}/100)."
        return f"{verdict} {reasons[0]}"
