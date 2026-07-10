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


# ── Resume Library (Phase 7.1) ─────────────────────────────────────────────────

class ResumeParseStatus(str, Enum):
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"


class Resume(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    original_filename: str
    stored_filename: str = Field(index=True)  # UUID-based — never trust user input for file paths
    version_name: str
    file_type: str  # "pdf" | "docx"
    is_active: bool = False
    parse_status: ResumeParseStatus = ResumeParseStatus.PENDING
    parser_version: Optional[str] = None
    parse_error: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    raw_text: Optional[str] = None

    # Parsed contact/profile fields
    parsed_name: Optional[str] = None
    parsed_email: Optional[str] = None
    parsed_phone: Optional[str] = None
    parsed_linkedin: Optional[str] = None
    parsed_portfolio: Optional[str] = None

    # Parsed structured data — JSON-encoded, decoded into ResumeResponse for the API
    parsed_skills: Optional[str] = None       # JSON list[str]
    parsed_companies: Optional[str] = None    # JSON list[str]
    parsed_job_titles: Optional[str] = None   # JSON list[str]
    parsed_education: Optional[str] = None    # JSON list[dict]
    parsed_experience: Optional[str] = None   # JSON list[dict]


class ResumeUpdate(SQLModel):
    """Fields that can be changed via PATCH /resumes/{id} — rename plus manual
    corrections to whatever the parser got wrong. No AI rewriting in this phase."""
    version_name: Optional[str] = Field(default=None, max_length=255)
    parsed_name: Optional[str] = Field(default=None, max_length=255)
    parsed_email: Optional[str] = Field(default=None, max_length=255)
    parsed_phone: Optional[str] = Field(default=None, max_length=100)
    parsed_linkedin: Optional[str] = Field(default=None, max_length=500)
    parsed_portfolio: Optional[str] = Field(default=None, max_length=500)
    parsed_skills: Optional[list[str]] = None
    parsed_companies: Optional[list[str]] = None
    parsed_job_titles: Optional[list[str]] = None
    parsed_education: Optional[list[dict]] = None
    parsed_experience: Optional[list[dict]] = None


class ResumeResponse(SQLModel):
    """Resume with JSON fields decoded into real lists — used for both the
    library list view and the detail view."""
    id: int
    original_filename: str
    version_name: str
    file_type: str
    is_active: bool
    parse_status: ResumeParseStatus
    parser_version: Optional[str]
    parse_error: Optional[str]
    uploaded_at: datetime
    updated_at: datetime
    raw_text: Optional[str]
    parsed_name: Optional[str]
    parsed_email: Optional[str]
    parsed_phone: Optional[str]
    parsed_linkedin: Optional[str]
    parsed_portfolio: Optional[str]
    parsed_skills: list[str] = []
    parsed_companies: list[str] = []
    parsed_job_titles: list[str] = []
    parsed_education: list[dict] = []
    parsed_experience: list[dict] = []
