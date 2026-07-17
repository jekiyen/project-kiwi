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
    # Kiwi Job Summary (Phase 7.6) — deterministic structured breakdown of
    # `description`, JSON-encoded (backend.job_summary.JobSummary). Never
    # overwrites description; regenerated whenever it changes.
    summary_json: Optional[str] = None
    # Application Copilot (Phase 8) — stamped whenever the Cover Letter
    # prompt is generated for this job via the Prompt Engine. Kiwi never
    # stores the AI's actual output (it's pasted into Claude by hand), so
    # this timestamp is the only signal the Readiness Engine can use for
    # "has a cover letter been prepared for this job."
    cover_letter_generated_at: Optional[datetime] = None


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
    """Timeline/history entry recording a lifecycle event for an application.

    event_type values: "created" | "status_change" | "note_updated" |
    "session_started" | "session_resumed" | "session_completed" |
    "session_cancelled" (Phase 8 — Application Session lifecycle)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="application.id", index=True)
    event_type: str
    from_status: Optional[ApplicationStatus] = None
    to_status: Optional[ApplicationStatus] = None
    detail: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ApplicationSessionStatus(str, Enum):
    STARTED   = "started"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ApplicationSession(SQLModel, table=True):
    """Application Copilot (Phase 8) — tracks a single "Launch Application"
    attempt. Kiwi only ever opens the employer's job URL in a new tab; it
    never submits anything. This is purely a record of when the user went to
    go apply and what they told Kiwi happened when they came back."""
    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="application.id", index=True)
    status: ApplicationSessionStatus = ApplicationSessionStatus.STARTED
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_opened_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    # Snapshots of what was used at launch time — never a copy of the actual
    # documents/data, just a human-readable marker of "what version was this."
    resume_version: Optional[str] = None
    cover_letter_version: Optional[str] = None
    profile_version: Optional[str] = None


class ApplicationSessionResponse(SQLModel):
    id: int
    application_id: int
    status: ApplicationSessionStatus
    started_at: datetime
    last_opened_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: int
    resume_version: Optional[str]
    cover_letter_version: Optional[str]
    profile_version: Optional[str]


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
    # Phase 8 — set when a not-yet-terminal (STARTED) ApplicationSession
    # exists for this application, so the Dashboard can show "Preparing"
    # instead of "Saved" without a second round trip per job.
    active_session_status: Optional[str] = None


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


# ── Application Profile (Phase 8.0) ──────────────────────────────────────────
# Single source of truth for reusable applicant information — the foundation
# future ATS autofill will read from. Exactly one row ever exists; the API
# upserts it rather than exposing multiple records. Resume data is never
# duplicated here — the Resume Vault remains the source of truth for that.

class ApplicationProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # Personal Information
    full_name: Optional[str] = None
    preferred_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    current_address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    nationality: Optional[str] = None
    # Work Rights
    work_rights_current_country: Optional[str] = None
    visa_status: Optional[str] = None
    eligible_to_work_nz: bool = False
    need_sponsorship: bool = False
    driver_license: bool = False
    own_vehicle: bool = False
    # Professional Links
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    github_url: Optional[str] = None
    website_url: Optional[str] = None
    # Emergency Contact
    emergency_contact_name: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    # Notes
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ApplicationReference(SQLModel, table=True):
    """A reference entry belonging to the single ApplicationProfile. Replaced
    wholesale on every PUT /application-profile — no separate CRUD routes."""
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="applicationprofile.id", index=True)
    name: str
    company: Optional[str] = None
    relationship: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


# ── Request / response models (not DB tables) ────────────────────────────────

class ApplicationReferenceInput(SQLModel):
    name: str = Field(max_length=255)
    company: Optional[str] = Field(default=None, max_length=255)
    relationship: Optional[str] = Field(default=None, max_length=255)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)


class ApplicationReferenceOut(ApplicationReferenceInput):
    id: int


class ApplicationProfileUpdate(SQLModel):
    """Full replace body for PUT /application-profile — every field is
    optional so the profile can be filled in progressively, and `references`
    always fully replaces the existing reference list."""
    # Personal Information
    full_name: Optional[str] = Field(default=None, max_length=255)
    preferred_name: Optional[str] = Field(default=None, max_length=255)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    current_address: Optional[str] = Field(default=None, max_length=500)
    city: Optional[str] = Field(default=None, max_length=255)
    country: Optional[str] = Field(default=None, max_length=255)
    nationality: Optional[str] = Field(default=None, max_length=255)
    # Work Rights
    work_rights_current_country: Optional[str] = Field(default=None, max_length=255)
    visa_status: Optional[str] = Field(default=None, max_length=255)
    eligible_to_work_nz: bool = False
    need_sponsorship: bool = False
    driver_license: bool = False
    own_vehicle: bool = False
    # Professional Links
    linkedin_url: Optional[str] = Field(default=None, max_length=500)
    portfolio_url: Optional[str] = Field(default=None, max_length=500)
    github_url: Optional[str] = Field(default=None, max_length=500)
    website_url: Optional[str] = Field(default=None, max_length=500)
    # Emergency Contact
    emergency_contact_name: Optional[str] = Field(default=None, max_length=255)
    emergency_contact_relationship: Optional[str] = Field(default=None, max_length=255)
    emergency_contact_phone: Optional[str] = Field(default=None, max_length=50)
    # Notes
    notes: Optional[str] = Field(default=None, max_length=5000)
    # References — full replace
    references: list[ApplicationReferenceInput] = []


class ApplicationProfileResponse(SQLModel):
    id: int
    full_name: Optional[str]
    preferred_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    current_address: Optional[str]
    city: Optional[str]
    country: Optional[str]
    nationality: Optional[str]
    work_rights_current_country: Optional[str]
    visa_status: Optional[str]
    eligible_to_work_nz: bool
    need_sponsorship: bool
    driver_license: bool
    own_vehicle: bool
    linkedin_url: Optional[str]
    portfolio_url: Optional[str]
    github_url: Optional[str]
    website_url: Optional[str]
    emergency_contact_name: Optional[str]
    emergency_contact_relationship: Optional[str]
    emergency_contact_phone: Optional[str]
    notes: Optional[str]
    references: list[ApplicationReferenceOut]
    created_at: datetime
    updated_at: datetime


# ── Application Copilot (Phase 8) ────────────────────────────────────────────
# Response shapes for the Application Readiness Engine and the Application
# Kit — see backend/core/application_readiness.py for the actual rules.

class SectionReadinessOut(SQLModel):
    resume: bool
    application_profile: bool
    cover_letter: bool
    references: bool
    work_rights: bool


class ApplicationReadinessResponse(SQLModel):
    status: str
    sections: SectionReadinessOut
    missing: list[str]
    score: int
    estimated_minutes: int


class ApplicationKitResponse(SQLModel):
    """Everything the Application Kit UI needs for one job, in one call."""
    readiness: ApplicationReadinessResponse
    application: Optional[Application]
    active_session: Optional[ApplicationSessionResponse]


class LaunchApplicationResponse(SQLModel):
    url: str
    application: Application
    session: ApplicationSessionResponse


class CompleteSessionRequest(SQLModel):
    outcome: str  # "applied" | "not_yet" | "cancelled"


class CompleteSessionResponse(SQLModel):
    application: Application
    session: ApplicationSessionResponse
