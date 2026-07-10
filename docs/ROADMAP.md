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

### Phase 6.1 — Application Intelligence
**Status:** Complete

- Application tracker: Saved / Applied / Interview / Offer / Rejected (+ Visa / Archived)
- Resume version and cover letter version tracked per application
- Per-application timeline/history (created, status changes)
- One-click Save / Apply from the Jobs page
- `GET /applications/{id}/timeline` endpoint

### Phase 6.2A — Telegram Notification Foundation
**Status:** Complete

- `NotificationService` + `NotificationProvider` abstraction (provider-agnostic; Email/Discord/Slack can be added without touching business logic)
- `TelegramProvider` — silently skips and logs a warning when unconfigured, never throws, never crashes a scan
- Event types: `HIGH_SCORE_JOB`, `SCAN_COMPLETED`, `SCAN_FAILED`, `APPLICATION_CREATED`, `APPLICATION_STATUS_CHANGED`
- Event dispatch wired into the scan agent and application/job routes (business logic never calls a provider directly)
- Production-ready message templates per event type
- `GET /api/v1/notifications/config`, `POST /api/v1/notifications/test`
- Notification Settings page + Dashboard health card (Telegram: Configured / Not Configured)
- Every send attempt logged (provider, event, success, duration, error) to `logs/notifications.log`
- `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` config — all optional, no user setup required yet

### Phase 6.2B — Live Telegram Integration
**Status:** Complete

- `TelegramProvider.check_connection()` — live `getMe()` health check, separate from the fast local `is_configured()` used on every dispatch
- `TelegramProvider.detect_chats()` — reads `getUpdates` to surface candidate chat IDs; never writes `TELEGRAM_CHAT_ID` automatically
- `GET /api/v1/notifications/chat-id` — chat ID detection endpoint (bot token → detected chats, or a friendly reason why not)
- `POST /api/v1/notifications/test` sends the real `"🥝 Kiwi Test"` message with a live timestamp when configured; returns exactly which `.env` vars are missing when not
- `GET /api/v1/notifications/config` now reports bot token presence, live bot connectivity, and chat ID presence separately
- Startup log line per provider: `ACTIVE` or `DISABLED` (local check, no network call at boot)
- Notifications page: Bot Status (Connected/Disconnected), Chat ID (Detected/Not Configured), Detect Chat ID button
- `docs/TELEGRAM_SETUP.md` rewritten around the in-app detection flow; README links it
- 35 new backend tests — chat detection, bad token, missing vars, provider active/disabled, mocked Telegram API throughout (no real network calls in the suite)

### Phase 6.3 — Final Hardening
**Status:** Complete

- Global FastAPI error handlers — consistent `{error, message}` shape on every failure, tracebacks never reach the client
- Startup config validation (`backend/config/validate.py`) — fails fast on unimplemented/misconfigured AI provider, bad scan interval, bad threshold; Telegram stays fully optional
- Bounded retry (`backend/core/retry.py`) — Telegram sends retry transient `NetworkError`/`TimedOut` only; scraper runs get one retry on a full failure. Never infinite.
- Request-ID middleware — every response carries `X-Request-ID`; every log line during that request is tagged with it; method/path/status/duration logged per request
- Asia/Jakarta (GMT+7) is now the display timezone everywhere: API timestamps, log lines (`backend/core/timezone.py`), the Telegram test message, the scheduler's own clock, and the frontend's `formatDate`. Storage stays UTC.
- Scheduler hardened: explicit `max_instances=1` / `coalesce=True` so a slow scan can't overlap itself; `POST /scans/trigger` now returns 409 if a scan is already running instead of racing scrapers against each other
- Fixed a real bug: `migrations/env.py` was missing `ApplicationEvent`, so `alembic revision --autogenerate` would have silently dropped it
- Fixed a real atomicity gap: application-create flows used two separate commits (app row, then its timeline event) — now a single `flush()` + one commit, so a crash between them can't leave an application with no history
- Fixed a real bug found during verification: the test suite wasn't hermetic — a developer with real Telegram credentials in `.env` (i.e. after completing 6.2B) had every test run silently message their own Telegram chat and made the suite ~30x slower. Added `tests/conftest.py` to force Telegram off by default.
- Fixed a real bug found during verification: the log formatter double-applied the GMT+7 offset on hosts whose system timezone was already Asia/Jakarta, showing timestamps 7 hours ahead of actual time.
- Frontend: `ErrorBoundary` around the whole app (a render crash no longer blanks the page), a missing error state on the Applications list added, a shared toast system (`useToast`) wired into Dashboard/Applications/Notifications mutations, and API error responses now surface the backend's actual message instead of a generic status code
- Defense-in-depth: bot token redacted from any logged/returned Telegram error text
- 22 new backend tests (config validation, error handling/request ID, GMT+7 log formatting) — full suite: 256 passed
- Verified live: real Telegram test notification delivered end-to-end after all changes, correct WIB timestamp

**Known remaining debt (not blocking, tracked for later):** ~83 pre-existing `Optional[X]` → `X | None` style lint findings across the codebase (cosmetic, out of scope for this pass); no automated frontend component tests yet (verification here was Playwright smoke + manual); scrapers retry once at the orchestration level but don't yet have per-request retry/backoff inside each scraper.

---

## Post-V1 Phases

### Phase 7 — Resume Intelligence

#### Phase 7.1 — Resume Library & Resume Intelligence Foundation
**Status:** Complete

- `Resume` model: original filename, version name, upload date, active flag, parse status, parser version, extracted text, parsed profile fields
- PDF upload (`pypdf`) and DOCX upload (`python-docx`), files stored under server-generated UUID names — original filenames are display metadata only, never trusted for file paths
- `RegexResumeParser` — deterministic, no AI: name, email, phone, LinkedIn, portfolio, skills, companies, job titles, education, experience (with dates and descriptions)
- Parser is behind a `ResumeParser` interface (`backend/resume/base.py`) with a single switch point (`get_resume_parser()`) — a Phase 7.2 AI-based parser plugs in without touching the API, storage, or frontend
- API: `GET/POST /resumes/`, `GET/PATCH/DELETE /resumes/{id}`, `POST /resumes/{id}/activate` (exactly one resume active at a time)
- Frontend: new **Resume** sidebar page — library with upload, active/parse-status badges, rename, delete, set-active; detail panel with manual editing of every parsed field (profile fields, skills, experience entries, education entries) — no AI rewriting in this phase
- 46 new backend tests (parser field extraction, text extraction from real generated PDF/DOCX fixtures, full upload/CRUD/activate lifecycle)

**Real bugs found and fixed during verification:**
- The block-grouping heuristic split one job entry into two whenever the date range sat on its own line, silently dropping the description. Fixed and covered by a regression test.
- Portfolio-URL extraction matched inside the email address itself (`rizky.pratama` from `rizky.pratama@email.com`) because the URL regex doesn't know about `@`. Fixed by blanking the matched email out of the search text first.
- **Security:** `httpx` (used internally by python-telegram-bot) logs full request URLs at INFO level — for the Telegram Bot API that URL contains the bot token in the path, leaking it straight to console/log output and bypassing the Phase 6.3 `redact_token()` defense entirely. Fixed with a `SecretRedactionFilter` applied to every log handler, plus raising `httpx`/`httpcore` to WARNING.

#### Phase 7.2 — AI Resume Analysis
**Status:** Next milestone

- AI-based `ResumeParser` implementation (higher accuracy than the regex parser, same interface)
- Keyword gap analysis: resume vs. job description
- Cover letter generation tailored per job description
- User approval workflow for all AI-suggested changes

### Phase 8 — Automated Applications
- Web form detection and auto-fill per employer site
- Email application sending with tailored content
- Application confirmation and receipt tracking

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
