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

### Phase 7 — Resume Vault

#### Phase 7.1 — Resume Library & Resume Intelligence Foundation
**Status:** Superseded by Phase 7.3 (kept here as a record of what shipped and why it changed)

- `Resume` model, PDF/DOCX upload, a deterministic `RegexResumeParser`, and a `ResumeParser` interface for a future AI-based parser
- 46 new backend tests; two real bugs found and fixed during verification (job-entry block-grouping, portfolio-URL/email collision), plus a real Telegram-token-leak-via-httpx-logging security fix

#### Phase 7.2 — AI Resume Analysis
**Status:** Superseded by Phase 7.3 (kept here as a record of what shipped and why it changed)

- `AIResumeParser` — sent extracted resume text to the configured AI provider (`AIProvider.extract_json`, new method), validated the response against a strict Pydantic schema, and fell back to the regex parser on any failure so malformed data was never persisted
- 18 new backend tests, all AI calls mocked

**Why 7.1 and 7.2 were superseded:** both tried to convert resumes into structured JSON — a real parsing pipeline that shipped and worked, but the product owner reviewed it and decided it didn't fit Kiwi's actual use. Kiwi is a personal desktop tool for one user, not a SaaS product; depending on a paid AI API just to parse resumes added ongoing cost and complexity for no real benefit. The resume document itself is the source of truth — AI analysis happens manually later by attaching it directly in Claude, not through an automated extraction pipeline. See Phase 7.3.

#### Phase 7.3 — Resume Vault
**Status:** Complete

- `Resume` model stripped to pure file metadata: `id`, `original_filename`, `filename` (renameable), `file_type`, `file_size`, `is_active`, `uploaded_at`, `updated_at` — no parsed data of any kind
- Migration `006_resume_vault.py` dropped all 15 parsing-related columns, backfilled `filename` from the old `version_name` and `file_size` by reading the real file on disk — ran cleanly against the one real resume already in the database, verified byte-for-byte after migrating
- `backend/resume/` package (regex parser, AI parser, text extraction, `ResumeParser` interface) deleted entirely — no parser abstraction needed for a vault; `extract_json` removed from `AIProvider` since it existed solely to support resume parsing
- API: `POST /resumes/upload` now stores metadata only (no extraction), `POST /resumes/{id}/replace` swaps the file while keeping the same id/name/active status, `GET /resumes/{id}/preview` (inline) and `GET /resumes/{id}/download` (attachment, original filename) serve the stored document directly, plus the existing list/detail/rename/activate/delete
- Frontend: Resume page rebuilt as a vault — Active Resume section + Other Resumes list, each card with Preview / Download / Replace / Set Active / Rename / Delete. Every structured-data editor (skills, experience, education, contact fields) removed.
- 33 new backend tests covering vault CRUD, replace, preview, and download — zero parsing tests remain
- **Future integration (explicitly out of scope for now):** a later Job Analysis workflow will use the Active Resume document together with a job description to generate a prompt for manual use in Claude — no automated extraction pipeline.

#### Phase 7.4 — Prompt Engine & AI Workspace
**Status:** Complete

Architectural foundation for every future AI-assisted workflow in Kiwi — not an AI feature itself. Kiwi still never calls an AI provider directly: it renders a prompt as plain text for the user to copy and paste into Claude by hand.

- `backend/prompt_engine/` — `render_template()` loads a Markdown template from `backend/prompt_engine/templates/` and substitutes `{{placeholder}}` variables via regex; a missing variable renders a visible `[name not provided]` marker rather than raising. Zero prompt text lives in Python.
- Actions are entirely configuration-driven: `registry.py` loads `backend/prompt_engine/actions.json` at import time (id, label, description, template_file, icon) — adding a new AI workflow requires only a new Markdown template + one JSON entry, no Python changes, no frontend or route changes.
- Six initial templates: Resume Analysis, Resume Improvement, Cover Letter, Interview Prep, Recruiter Message, Salary Negotiation — each pulls job title/employer/location/description and the active Resume Vault filename into the prompt.
- API: `GET /prompts/actions` lists the registry; `GET /jobs/{id}/prompts/{action_id}` renders a job-scoped prompt (404 on unknown job or action); `GET /jobs/{id}/changes` returns job change history, newest first.
- New dedicated Job Detail page at `/jobs/:id` with `Description | AI Workspace | Activity` tabs, replacing the previous flat job-card-only view. The AI Workspace tab renders action tiles from the registry inside a `WorkspaceSection` wrapper designed to hold future sections (Analysis History, Saved AI Results, Visa Guidance, etc.) without reshaping the page.
- `PromptPreviewModal` — title, scrollable rendered prompt, Copy Prompt (clipboard + toast) / Open Claude (`claude.ai/new` in a new tab) / Cancel. No automatic communication with Claude at any point.
- 18 new backend tests (template rendering, config-driven registry loading, both new endpoints incl. 404s and missing-resume/description fallbacks) — full suite: 310 passed. Verified live with Playwright: navigated a real job to its detail page, switched all three tabs, generated a Cover Letter prompt against real job + active resume data, copied it to the clipboard (verified via `navigator.clipboard.readText()`), and confirmed the Activity tab's empty state — zero console errors throughout.

#### Phase 7.5 — AI Readiness & Job Quality
**Status:** Complete

Stops the AI Workspace from silently generating a low-quality prompt from incomplete job data — the system now says why confidence is limited instead of guessing anyway.

- `backend/core/ai_readiness.py` — single `evaluate_ai_readiness(job, active_resume)` evaluator used by both the readiness card endpoint and the Prompt Guard, so they can never disagree. Hard requirements (Job Title, Company, Active Resume) missing → `not_ready` (generation blocked entirely); only Job Description missing → `partial` (generation allowed with a disclaimer); everything present → `ready`.
- API: `GET /jobs/{id}/ai-readiness` (status/missing/impact) and `PATCH /jobs/{id}` (Edit Job fast path — title/employer/location/description; logs a `JobChange` row per changed field so manual edits show up in the Activity tab for free).
- Prompt Guard lives inside `GET /jobs/{id}/prompts/{action_id}`: returns 409 without generating anything when Not Ready; when Partial, injects an explicit anti-hallucination instruction into the rendered prompt text itself ("do not invent or assume... clearly note limited confidence") plus a separate `disclaimer` field for the UI — the guardrail travels with the copied prompt, not just the screen.
- Frontend: an `AIReadinessCard` at the top of the AI Workspace tab (status badge, missing list, impact sentence, Edit Job / Go to Resume Vault actions) drives an inline edit form — no modal, no leaving the tab — and gates the action tiles (`disabled` when Not Ready). `PromptPreviewModal` shows a yellow disclaimer banner when the generated prompt is Partial.
- 19 new backend tests (evaluator rules incl. priority of Not Ready over Partial, both endpoints, Prompt Guard 409/disclaimer paths, PATCH incl. JobChange logging and no-op-when-unchanged) — full suite: 329 passed. Verified live with Playwright against real job data: confirmed action tiles are actually disabled (not just styled) when Not Ready, used the inline Edit Job form to fix a missing field and watched the card transition Not Ready → Partial in place, generated a prompt in each of the three states and confirmed the disclaimer banner and embedded guardrail text appear only when Partial — zero console errors throughout.

#### Phase 7.6 — Job Intelligence
**Status:** Complete

Turns every scraped job description into a structured "Kiwi Job Summary" before it reaches the AI Workspace — deterministic regex/heading extraction only, no LLM, no external API. Missing values stay empty; nothing is ever invented.

- `backend/job_summary/` — `generate_job_summary(description, salary_text)` detects section headings (Responsibilities, Requirements, Preferred, Benefits, Working Conditions, Salary, ~40 recognized phrase variants total) via whole-line `fullmatch` so a sentence like "3+ years of experience" can never be mistaken for a heading. Splits each section into bullet items, pulls salary via a dedicated regex plus a heading-section preference, and extracts visa-related sentences (`visa`, `sponsorship`, `work rights`, `eligib*`, `citizen`, `residency`) verbatim. When no headings exist at all, falls back conservatively: real bullet-marked lines go to Responsibilities (with a warning explaining why nothing was categorized further), plain prose goes to Overview untouched — it never guesses which fallback bullets are requirements vs. responsibilities. Self-diagnostic `warnings[]` flag what couldn't be found (no responsibilities/requirements/salary/sections).
- `Job.summary_json` (migration `007_job_summary.py`, additive/nullable — `description` is never overwritten) is generated automatically on scraper ingestion (`scan_agent.py`) and regenerated whenever `description` changes via the Edit Job fast path (Phase 7.5). Legacy jobs from before this phase get one lazily on first read (`GET /jobs/{id}/summary`, write-through) rather than needing a bulk backfill migration.
- Prompt Guard (`generate_job_prompt`) now consumes the structured summary via `render_summary_as_text()` instead of the raw description whenever the summary has any content, falling back to raw `description` (then the Phase 7.5 missing-description guardrail) only when the summary is genuinely empty — exactly mirrors what the AI Workspace itself shows the user.
- Frontend: the old single Description tab is now five tabs. **Overview** — a Quick Facts grid (Job Title, Company, Location, Employment Type ["Not specified" — no such field exists on Job, stated honestly rather than guessed], Salary, Visa Status shown only when available) plus the extracted overview paragraph. **AI Summary** — Responsibilities / Required Qualifications / Preferred Qualifications / Benefits / Work Environment / Warnings as labelled cards, each hidden entirely when empty rather than rendering blank. **Original Description** — the untouched raw text with a Copy-to-clipboard button, expand/collapse for long text (>600 chars, gradient-faded when collapsed), and preserved line breaks/whitespace. **Activity** — no longer just a raw `JobChange` diff list: synthesizes "Job discovered," "AI analysis completed" (with score), and "Seen again in a scan" milestones from the job's own timestamps and merges them chronologically with real change events, so a freshly-scraped job with zero edits still shows a meaningful timeline instead of an empty page. Overview and AI Summary both auto-fall-back to the same raw-description card (with a small notice) when the summary comes back empty or the request fails.
- 29 new backend tests (heading detection incl. the false-positive-on-prose case, all fallback branches, `is_empty()`, the text formatter, the two API endpoints, PATCH-triggered regeneration, Prompt Guard now sourcing from the summary) — full suite: 358 passed. Verified live with Playwright against real (self-healing legacy) job data across two rounds: first the backend wiring end-to-end, then a follow-up pass specifically on tab content — confirmed Quick Facts render correctly, all AI Summary sections populate with empty ones hidden, Original Description's expand/collapse and clipboard copy both work with formatting intact, and the Activity timeline shows synthesized milestones even for a job with zero real changes — zero console errors throughout. Test edits made to real jobs during verification were reverted afterward.

### Phase 8 — Application Copilot
**Status:** Complete

Transforms Kiwi from a Job Tracker into an Application Copilot: it reduces the effort of applying to NZ jobs while keeping the applicant fully in control. Kiwi assists — it never submits an application automatically. The user always launches, fills in, and submits the employer's own form; Kiwi only prepares, tracks, and follows up.

- **Application Profile** — the single source of truth for reusable applicant information, and the foundation everything else in this phase reads from. A singleton `ApplicationProfile` table (migration `008_application_profile.py`; the API upserts the one existing row rather than exposing multiple records, created lazily on first `GET`) covering Personal Information, Work Rights, Professional Links, Emergency Contact, and free-text Notes, plus a separate `ApplicationReference` table fully replaced on every `PUT`. API: `GET`/`PUT /application-profile` (two endpoints total). Resume data is never duplicated — the profile's Resume section reads the Active Resume from the Resume Vault and links back to it. New `/application-profile` page and sidebar nav item, sections as cards, a single "Save Profile" action.
- **Application Readiness Engine** (`backend/core/application_readiness.py`) — the single deterministic evaluator for "is the user ready to apply to this job," used everywhere and never re-implemented: NOT_READY when the active Resume or a filled-in Application Profile is missing; PARTIAL when the Cover Letter, References, Phone Number, Driver License, or Work Rights are missing; READY otherwise. Produces a 0–100 score and a rough estimated-completion-time in minutes alongside the missing-item list.
- **Application Kit** (`GET /jobs/{id}/application-kit`) — replaces the old instant "Apply" button. Shows Resume / Cover Letter / Application Profile / References / Work Rights readiness per section (each linking straight to where it can be fixed), the Readiness Score, Estimated Completion Time, and Missing Information. `Job.cover_letter_generated_at` (migration `009_application_copilot.py`) is stamped whenever the Cover Letter prompt is generated in the AI Workspace — Kiwi never stores the AI's actual output, so this timestamp is the only signal the engine has for "a cover letter has been prepared."
- **Launch Application** (`POST /jobs/{id}/launch-application`) — opens the original job URL in a new tab. Never auto-submits, never clicks anything, never uploads anything. Creates the `Application` record if one doesn't exist yet and starts (or resumes) an `ApplicationSession`.
- **Application Session** (`ApplicationSession` table) — tracks Started, Last Opened, Duration, Current Status (started/completed/cancelled), and snapshots of the Resume/Cover Letter/Profile versions in use at launch time.
- **Manual Completion** (`POST /jobs/{id}/application-session/complete`) — Kiwi never guesses whether an application was submitted. Coming back from the employer's site surfaces "Did you successfully submit this application?" with Applied / Not Yet / Cancelled — only the user decides. Applied moves the underlying `Application.status` to `applied` (reusing the existing status-change + notification path); Cancelled leaves it untouched; Not Yet leaves the session open to resume later.
- **Timeline** — Application Session lifecycle events (`session_started`, `session_resumed`, `session_completed`, `session_cancelled`) are logged as `ApplicationEvent` rows and merged into both the Job Detail page's Activity tab (alongside job-discovery/change milestones) and the Applications page's per-application timeline — one event log, two views.
- **Dashboard** — the Jobs page now shows a live workflow badge per job (Ready / Preparing / Applied / Interview / Offer / Rejected / …), computed from the same Readiness Engine (bulk `GET /jobs/readiness-summary`, one query for every active job) plus each job's real `ApplicationStatus` and any in-progress session — never a second copy of the rules.
- Fixed a related correctness gap while wiring this up: `DELETE /applications/{id}` previously left orphaned `ApplicationSession` rows behind; it now cascades to delete those too.
- 37 new backend tests (Readiness Engine unit tests for every rule, Application Kit / readiness-summary / launch / complete-session endpoints incl. all three outcomes, cover-letter stamping, the cascade-delete fix) — full suite: 412 passed. Frontend: clean `tsc` + `vite build`. Verified live against the running dev backend end-to-end (launch → resume → application-kit → complete with each outcome → readiness-summary reflects the change), then reverted the test application/session so no fake activity was left on a real job.

### Phase 9 — Job Intelligence
**Status:** Complete

Not to be confused with Phase 7.6 (also "Job Intelligence" — that phase extracts structure *out of one job's description*; this phase decides *which jobs are worth applying to*). Helps the user decide WHAT to apply for next: prioritizes jobs, explains why, and surfaces missing requirements — all deterministic, all reusing data Kiwi already has. Never calls an AI provider, never hallucinates a score or a missing item.

- **Job Intelligence service** (`backend/core/job_intelligence.py`) — the single evaluator, used everywhere. It's an interpretation layer, not a second scorer: when a job has already been analysed, it reads `Job.ai_match_score` / `ai_confidence` / `ai_reasons` (ManualProvider's existing deterministic keyword analysis, Phase 3) as-is; for a job that hasn't been analysed yet, it falls back to `backend/core/matcher.py`'s structured-fields-only score (role priority + visa flags) rather than inventing a new formula. Produces **Score**, **Confidence**, and a plain-language **Reason list**.
- **Recommendation Badge** — score bucketed into Highly Recommended (≥80) / Recommended (≥60) / Consider (≥35) / Low Priority (below), via one threshold function (`recommendation_for_score`).
- **Missing Requirements** — what the listing itself didn't specify (Requirements, Salary, Employment Type, Job Description, Visa/Work Rights Policy), each literally `"<field>: Not specified"` when absent — never a guess, and never a comparison against the applicant's own qualifications (which would risk inventing a match).
- **Priority Queue** — a new "Priority Queue (recommendation)" Dashboard sort option, backed by the bulk `GET /jobs/job-intelligence-summary` (one query for every active job, computed once).
- **Similar Jobs** (`GET /jobs/{id}/similar`) — deterministic similarity by Title (token overlap), Industry (role priority — the closest proxy Kiwi has, since no job source provides a real industry field), and Location; Employment Type is intentionally skipped since no job source provides it.
- **Why This Job** — the Reason list rendered as its own card on the Job Detail Overview tab, next to the new Score/Confidence/Recommendation card and the Missing Requirements and Similar Jobs cards.
- **Jobs Filters** — Ready / High Match / Visa Compatible / Applied filter chips on the Dashboard, combining the Phase 8 Readiness Engine, this phase's recommendation summary, and existing visa flags / application status — no new rules, just composition.
- **AI Workspace** — a new "Why am I a good fit?" prompt action (`good_fit.md` + one `actions.json` entry — zero code changes needed thanks to the Phase 7.4 config-driven registry), grounded in this phase's deterministic reasons via a new `match_reasons` template variable. Still only ever renders a prompt for the user to paste into Claude by hand — never calls an AI API.
- Fixed while wiring this up: nothing — no regressions found needing a fix this phase.
- 33 new backend tests (recommendation thresholds, scoring incl. the analysed/fallback paths, reasons incl. malformed-JSON resilience, missing-requirements gap detection, similarity matching/exclusion/limit, all three new endpoints, the new Prompt Engine action) — full suite: 445 passed. Frontend: clean `tsc` + `vite build`. Verified live against the running dev backend across real data (1,435 active jobs): job-intelligence, the bulk summary, similar-jobs, and the good_fit prompt (incl. its Prompt Guard disclaimer) all returned correct, consistent results.

### Phase 10 — Interview Copilot
- Interview preparation workspace once an application reaches the Interview stage
- Likely-questions and talking-points generation via the existing Prompt Engine (no new AI integration)
- Interview scheduling/reminders surfaced through existing notifications
- Post-interview follow-up tracking integrated into the existing Activity timeline

### Phase 11 — Visa Advisor
- Accredited Employer Work Visa pathway guide
- Working Holiday Visa eligibility checker
- Document checklist per visa type
- Timeline estimator for visa processing

### Phase 12 — Cloud Deployment
- Dockerize all services
- Deploy to VPS with persistent storage
- Remote dashboard access (secured)
- Cloud-scheduled scanning (no local machine required)

### Phase 13 — Settlement Assistant
- Housing research by NZ region
- Cost of living calculator
- Community guides for regions with high seasonal work
- Family relocation planning checklist
