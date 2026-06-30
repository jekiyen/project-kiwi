from sqlmodel import Session

from backend.database.models import Job
from backend.database.queries import get_job_by_external_id


def is_duplicate(session: Session, external_id: str, source: str) -> bool:
    return get_job_by_external_id(session, external_id, source) is not None


def find_changes(existing: Job, incoming: dict) -> dict[str, tuple[str, str]]:
    """Return a dict of {field: (old_value, new_value)} for changed fields."""
    watched = ["title", "salary_text", "description", "visa_accredited_employer"]
    changes = {}
    for field in watched:
        old = str(getattr(existing, field, ""))
        new = str(incoming.get(field, ""))
        if old != new:
            changes[field] = (old, new)
    return changes
