from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class RolePriority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class ApplicationStatus(str, Enum):
    SAVED      = "saved"
    APPLIED    = "applied"
    INTERVIEW  = "interview"
    OFFER      = "offer"
    REJECTED   = "rejected"
    VISA       = "visa"
    ARCHIVED   = "archived"


class ScanStatus(str, Enum):
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(index=True)
    source: str = Field(index=True)
    title: str
    employer: str
    location: str
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_text: Optional[str] = None
    description: Optional[str] = None
    url: str
    role_priority: Optional[RolePriority] = None
    # Visa eligibility tags
    visa_accredited_employer: bool = False
    visa_overseas_friendly: bool   = False
    visa_sponsorship_potential: bool = False
    visa_nz_rights_required: bool  = False
    # AI analysis — core
    ai_match_score: Optional[float] = None
    ai_explanation: Optional[str]   = None
    ai_analysed_at: Optional[datetime] = None
    # AI analysis — extended (Phase 3)
    ai_priority: Optional[str] = None
    ai_reasons: Optional[str]  = None
    ai_pros: Optional[str]     = None
    ai_cons: Optional[str]     = None
    ai_visa_probability: Optional[int] = None
    ai_confidence: Optional[int]       = None
    ai_provider: Optional[str]         = None
    ai_model: Optional[str]            = None
    # Metadata
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime  = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    raw_data: Optional[str] = None


class Application(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    status: ApplicationStatus = ApplicationStatus.SAVED
    notes: Optional[str] = None
    applied_at: Optional[datetime] = None
    interview_date: Optional[datetime] = None
    follow_up_date: Optional[datetime] = None
    resume_version: Optional[str] = None
    cover_letter_version: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ApplicationEvent(SQLModel, table=True):
    """Timeline/history entry recording a lifecycle event for an application."""
    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="application.id", index=True)
    event_type: str  # "created" | "status_change" | "note_updated"
    from_status: Optional[ApplicationStatus] = None
    to_status: Optional[ApplicationStatus] = None
    detail: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Request / response models (not DB tables) ─────────────────────────────────

class ApplicationUpdate(SQLModel):
    """Fields that can be changed via PATCH /applications/{id}."""
    status: Optional[ApplicationStatus] = None
    notes: Optional[str] = Field(default=None, max_length=5000)
    applied_at: Optional[datetime] = None
    interview_date: Optional[datetime] = None
    follow_up_date: Optional[datetime] = None
    resume_version: Optional[str] = Field(default=None, max_length=255)
    cover_letter_version: Optional[str] = Field(default=None, max_length=255)


class ApplicationWithJob(SQLModel):
    """Application record with embedded job details for list endpoints."""
    # Application fields
    id: int
    job_id: int
    status: ApplicationStatus
    notes: Optional[str]
    applied_at: Optional[datetime]
    interview_date: Optional[datetime]
    follow_up_date: Optional[datetime]
    resume_version: Optional[str]
    cover_letter_version: Optional[str]
    created_at: datetime
    updated_at: datetime
    # Job fields
    job_title: str
    job_employer: str
    job_location: str
    job_url: str
    job_source: str
    job_ai_match_score: Optional[float]
    job_role_priority: Optional[str]
    job_ai_priority: Optional[str]
    job_salary_text: Optional[str]


class PipelineCounts(SQLModel):
    """Count of applications per status stage."""
    saved: int = 0
    applied: int = 0
    interview: int = 0
    offer: int = 0
    rejected: int = 0
    visa: int = 0
    archived: int = 0
    total: int = 0


class Scan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    source: str = "all"
    jobs_found: int = 0
    new_jobs: int = 0
    changed_jobs: int = 0
    errors: Optional[str] = None
    status: ScanStatus = ScanStatus.RUNNING
    # Aggregate metrics added in Phase 5.5
    total_duplicates: int = 0
    total_errors: int = 0
    duration_ms: Optional[int] = None


class ScraperRun(SQLModel, table=True):
    """Per-scraper execution record within a Scan."""
    id: Optional[int] = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scan.id", index=True)
    source: str
    status: str = "success"   # success | partial | failed
    jobs_found: int = 0
    jobs_inserted: int = 0
    duplicates_skipped: int = 0
    errors: Optional[str] = None
    duration_ms: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None


# ── Response model (not a DB table) ──────────────────────────────────────────

class ScanDetail(SQLModel):
    """Scan with embedded per-scraper runs for the API response."""
    id: int
    started_at: datetime
    completed_at: Optional[datetime]
    source: str
    jobs_found: int
    new_jobs: int
    changed_jobs: int
    errors: Optional[str]
    status: ScanStatus
    total_duplicates: int
    total_errors: int
    duration_ms: Optional[int]
    scraper_runs: list[ScraperRun] = []


class JobChange(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    field_changed: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)


# ── Resume Vault (Phase 7.3) ────────────────────────────────────────────────────
# Kiwi stores resume documents as source-of-truth files, not structured data.
# No parsing, no AI extraction — see docs/ROADMAP.md Phase 7.3 for why.

class Resume(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    original_filename: str
    stored_filename: str = Field(index=True)  # UUID-based — never trust user input for file paths
    filename: str  # user-editable display name (rename)
    file_type: str  # "pdf" | "docx"
    file_size: int  # bytes
    is_active: bool = False
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ResumeUpdate(SQLModel):
    """Fields that can be changed via PATCH /resumes/{id} — rename only."""
    filename: Optional[str] = Field(default=None, max_length=255)


class ResumeResponse(SQLModel):
    id: int
    original_filename: str
    filename: str
    file_type: str
    file_size: int
    is_active: bool
    uploaded_at: datetime
    updated_at: datetime
