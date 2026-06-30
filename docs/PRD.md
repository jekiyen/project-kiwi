# Project Kiwi — Product Requirements Document

## Problem Statement

Searching for jobs in New Zealand as an overseas applicant is fragmented, repetitive, and opaque. Listings are spread across many platforms. Visa eligibility is rarely stated clearly. Tracking applications manually is error-prone. And for someone transitioning careers while planning an international relocation, the cognitive load is immense.

The result: hours spent each day on low-value search tasks, with no reliable system to prioritize what actually matters.

---

## Target User

**Single user: Rizky**

- Indonesian citizen, no current New Zealand work rights.
- Professional background in Product Design; intentionally transitioning to blue-collar work.
- English (professional working proficiency), Indonesian (native).
- Planning to relocate solo first, assess viability, then bring family.
- Non-engineer — relies on Claude Code for all development and maintenance.

---

## Scope

### In Scope — V1
- Blue-collar job discovery from 6 NZ platforms
- AI-powered job ranking and match explanation
- Visa eligibility tagging per listing
- Manual application status tracking
- Local web dashboard
- Telegram notifications for key events
- Resume ingestion as input (read-only in V1)
- 6-hour auto-scan and manual trigger
- Deduplication and change detection
- Scan activity logging

### Out of Scope — V1
- Automated job application submission
- Resume modification or rewriting
- Cover letter generation
- Visa application assistance
- Document preparation
- Mobile app
- Cloud deployment
- Family relocation planning

---

## Functional Requirements

### Job Discovery

| ID | Requirement |
|----|-------------|
| FR-01 | Scrape jobs from: SEEK NZ, Trade Me Jobs, PickNZ, Backpacker Board NZ, Seasonal Jobs NZ, Indeed NZ. |
| FR-02 | Filter for target roles by priority: P1 (Packhouse, Fruit Picker, Orchard, Farm Worker), P2 (Warehouse, Manufacturing, Factory Worker), P3 (Construction, General Labourer). |
| FR-03 | Auto-scan all sources every 6 hours. Support manual scan trigger from dashboard. |
| FR-04 | Detect and suppress duplicate listings (same job, same employer, same location). |
| FR-05 | Detect meaningful changes to existing listings (salary, visa info, closing date) and re-flag them. |
| FR-06 | Log all scan activity: timestamp, source, jobs found, new jobs, errors. |
| FR-07 | Scraper architecture must be extensible — adding a new source requires minimal code changes. |

### AI Ranking & Analysis

| ID | Requirement |
|----|-------------|
| FR-08 | Score each job against user profile (entry-level fit, language requirements, transferable skills). |
| FR-09 | Tag each job for visa eligibility: Accredited Employer, Overseas Applicants Welcome, Potential Sponsorship, NZ Work Rights Required. |
| FR-10 | Jobs requiring existing NZ work rights are marked low priority — not discarded. |
| FR-11 | Generate a short AI explanation for each job: why it matches or does not match the user's profile. |
| FR-12 | Cache AI results — only re-analyse jobs that are new or have changed, to control API costs. |

### Application Tracking

| ID | Requirement |
|----|-------------|
| FR-13 | User can manually set application status per job: Discovered → Saved → Applied → Interview → Offer → Rejected. |
| FR-14 | Application pipeline displayed on dashboard with current status per role. |

### Web Dashboard

| ID | Requirement |
|----|-------------|
| FR-15 | Display newly discovered jobs sorted by AI match score. |
| FR-16 | Display AI match explanation per job. |
| FR-17 | Display full application pipeline with status. |
| FR-18 | Display scan logs and system health (last scan time, errors, job counts). |
| FR-19 | Button to trigger manual scan. |

### Telegram Notifications

| ID | Requirement |
|----|-------------|
| FR-20 | Notify on new high-priority job matches (configurable score threshold). |
| FR-21 | Notify on application status changes. |
| FR-22 | Notify on scan errors or system failures. |
| FR-23 | Bot created via BotFather; setup documented step-by-step for reproducibility. |

### Resume

| ID | Requirement |
|----|-------------|
| FR-24 | Accept user's existing resume as input (PDF or plain text). |
| FR-25 | Use resume content to inform job matching and scoring. |
| FR-26 | Do not automatically modify the resume. All suggestions require explicit user approval. |

---

## Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | Runs entirely on a local macOS machine — no cloud infrastructure required in V1. |
| NFR-02 | Architecture must support deployment to a VPS or cloud server without major rework. |
| NFR-03 | No mandatory paid cloud services beyond Claude API (Anthropic). |
| NFR-04 | Dashboard loads within 2 seconds on local machine. |
| NFR-05 | Individual scraper failures must not stop the overall scan — log error, continue with remaining sources. |
| NFR-06 | System must be maintainable by Claude Code without requiring engineering expertise from the user. |
| NFR-07 | All data stored locally in a structured database. |

---

## Constraints

- User has no NZ work rights — every job must be evaluated with visa context.
- User is a non-engineer — configuration and UI must be simple and clear.
- No cloud spend in V1.
- System must run on macOS.
- Claude Pro / Anthropic API is the only approved AI backend.

---

## Assumptions

- Target platforms can be scraped without official API access.
- The NZ blue-collar job market (especially seasonal roles) has sufficient active listings to surface weekly matches.
- User will manually import their resume as the first setup step.
- Telegram BotFather process remains available for bot creation.
- Claude API latency is acceptable for batch job analysis (not real-time).

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Job platforms block scraping | Medium | High | Respectful scraping practices, rate limiting, user-agent rotation |
| Platform HTML structure changes break scrapers | Medium | Medium | Modular scraper design; error logging and alerting |
| Claude API costs grow unexpectedly | Low | Medium | Cache analysis results; only re-analyse new or changed listings |
| Poor match quality in early weeks | Medium | Medium | Iterative tuning of ranking prompts based on real usage |
| Telegram bot setup fails or is blocked | Low | Low | Dashboard is the primary interface; Telegram is supplementary |

---

## V1 Features

1. Multi-platform job scraper (6 sources)
2. AI job ranking and match explanation
3. Visa eligibility tagging per listing
4. Web dashboard: job feed, tracking, logs
5. Telegram notifications for high-priority events
6. Resume ingestion as read-only input
7. Manual application status tracking
8. 6-hour auto-scan + manual trigger
9. Deduplication and change detection
10. Scan activity logging

---

## Future Features

- Automated job application submission
- Tailored cover letter generation per role
- Resume keyword gap analysis and suggestions
- Multiple resume versions by job category
- User approval workflow for all AI-suggested resume changes
- Visa pathway advisor (Accredited Employer Work Visa, Working Holiday, etc.)
- Document preparation checklist
- Employer background research module
- VPS / cloud deployment with remote dashboard access
- Housing and cost-of-living research
- Settlement and community guides for New Zealand regions
