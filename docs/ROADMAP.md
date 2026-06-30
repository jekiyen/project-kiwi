# Project Kiwi — Roadmap

Development follows a phase-by-phase approach: each phase must be stable before the next begins. V1 is complete when Phase 6 is signed off.

---

## Phase 0 — Foundation
**Status:** In Progress
**Goal:** Establish project documentation and tech stack before writing any application code.

| Deliverable | Status |
|-------------|--------|
| Product interview | Done |
| VISION.md | Done |
| PRD.md | Done |
| ROADMAP.md | Done |
| README.md | Done |
| Tech stack decision | Pending |
| Project scaffolding | Pending |

---

## Phase 1 — Core Infrastructure
**Priority:** Critical
**Goal:** A running local system with database, scheduler, web server skeleton, and Telegram connected.

**Deliverables:**
- Local database setup and schema (jobs, scans, applications, logs)
- Project folder structure established
- Web server running locally (dashboard shell — no content yet)
- Scheduler configured: 6-hour auto-scan + manual trigger endpoint
- Structured logging system (scan activity, errors)
- Environment configuration (.env) with documented variables
- Telegram bot created via BotFather
- Bot connected to application
- Test notification sent and confirmed

**Done when:** Dashboard loads at localhost, scheduler runs on interval, and a test Telegram message is received.

---

## Phase 2 — Job Scrapers
**Priority:** Critical
**Goal:** Reliably collect job listings from all 6 target platforms.

**Deliverables:**
- Scraper: SEEK NZ
- Scraper: Trade Me Jobs
- Scraper: PickNZ
- Scraper: Backpacker Board NZ
- Scraper: Seasonal Jobs NZ
- Scraper: Indeed NZ
- Deduplication logic (same job, same employer, same location)
- Change detection logic (salary, visa info, closing date)
- Per-scraper error isolation (one failure does not stop others)
- Extensible scraper interface for future sources
- All results persisted to local database

**Done when:** All 6 scrapers run successfully, new jobs are stored, duplicates are skipped, and changes are flagged.

---

## Phase 3 — AI Analysis & Ranking
**Priority:** Critical
**Goal:** Every collected job is evaluated against the user profile and scored.

**Deliverables:**
- Resume ingestion (PDF and plain text support)
- Job-to-profile matching via Claude API
- Visa eligibility tagging: Accredited Employer, Overseas Applicants Welcome, Potential Sponsorship, NZ Work Rights Required
- Priority scoring: combines role priority (P1/P2/P3) with visa tags and profile fit
- Short AI match explanation generated per job
- Analysis results cached — only re-analyse new or changed listings

**Done when:** Every stored job has a match score, visa tags, and a plain-language explanation viewable in the database.

---

## Phase 4 — Web Dashboard
**Priority:** High
**Goal:** A functional local dashboard to review, filter, and manage jobs.

**Deliverables:**
- Job discovery feed sorted by match score
- Job detail view: title, employer, location, salary, visa tags, AI explanation, source link
- Application pipeline view: Discovered → Saved → Applied → Interview → Offer → Rejected
- Manual status update per job
- Scan log viewer: timestamp, source, counts, errors
- System health indicator: last scan time, next scan time
- Manual scan trigger button

**Done when:** User can open the dashboard, see ranked jobs, read AI explanations, update application status, and trigger a scan — all without touching the terminal.

---

## Phase 5 — Telegram Notifications
**Priority:** High
**Goal:** Real-time alerts for events that require attention.

**Deliverables:**
- High-priority match notification (configurable score threshold)
- Application status change notification
- Scan error or system failure notification
- Notification message format: clear, concise, actionable

**Done when:** A new high-priority job triggers a Telegram message within minutes of discovery.

---

## Phase 6 — V1 Hardening
**Priority:** High
**Goal:** Stable, reliable V1 ready for daily use as the primary job search tool.

**Deliverables:**
- End-to-end pipeline test (scrape → analyse → dashboard → notify)
- Error recovery and retry logic for failed scans
- Performance review (scan duration, API call count, cost estimate)
- README setup instructions completed and verified
- Telegram setup documented in docs/TELEGRAM_SETUP.md
- V1 sign-off: user confirms the system is replacing manual job search

---

## Post-V1 Phases

### Phase 7 — Automated Applications
- Web form detection and auto-fill per employer site
- Email application sending with tailored content
- Application confirmation and receipt tracking

### Phase 8 — Resume Intelligence
- Cover letter generation tailored per job description
- Keyword gap analysis: resume vs. job description
- Multiple resume versions by job category
- User approval workflow for all AI-suggested changes

### Phase 9 — Visa Advisor
- Accredited Employer Work Visa pathway guide
- Working Holiday Visa eligibility checker
- Document checklist per visa type
- Timeline estimator for visa processing

### Phase 10 — Cloud Deployment
- Dockerize all services
- Deploy to VPS with persistent storage
- Remote dashboard access (secured)
- Cloud-scheduled scanning (no local machine required)

### Phase 11 — Settlement Assistant
- Housing research by NZ region
- Cost of living calculator
- Community guides for regions with high seasonal work
- Family relocation planning checklist
