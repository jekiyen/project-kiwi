from backend.database.models import Job, RolePriority

PRIORITY_BASE_SCORE = {
    RolePriority.P1: 0.8,
    RolePriority.P2: 0.6,
    RolePriority.P3: 0.4,
}

_P1 = {"packhouse", "pack house", "picker", "picking", "orchard", "farm worker", "farm hand", "harvest", "horticulture", "kiwifruit", "pruning"}
_P2 = {"warehouse", "factory worker", "factory", "manufacturing", "production worker", "storeperson", "stores person"}
_P3 = {"labourer", "laborer", "construction labourer", "general labour", "general labor", "site labourer", "labour hire"}


def classify_role(title: str, description: str = "") -> RolePriority | None:
    """Classify a job into P1/P2/P3 priority based on title and description keywords."""
    text = (title + " " + description).lower()
    if any(k in text for k in _P1):
        return RolePriority.P1
    if any(k in text for k in _P2):
        return RolePriority.P2
    if any(k in text for k in _P3):
        return RolePriority.P3
    return None


def score_job(job: Job) -> float:
    """
    Compute a basic match score from structured fields only.
    Phase 3: this is supplemented/replaced by AIProvider.analyze_job().
    """
    score = PRIORITY_BASE_SCORE.get(job.role_priority, 0.3)
    if job.visa_accredited_employer:
        score = min(score + 0.1, 1.0)
    if job.visa_overseas_friendly:
        score = min(score + 0.1, 1.0)
    if job.visa_nz_rights_required:
        score = max(score - 0.3, 0.0)
    return round(score, 2)
