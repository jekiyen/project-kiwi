# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project

**Project Kiwi** is a personal AI migration copilot for one user (Rizky) migrating from Indonesia to New Zealand. It is a single-user local tool, not a public product.

V1 focuses on blue-collar job discovery, AI ranking, visa eligibility tagging, and application tracking.

Full context: `docs/VISION.md`, `docs/PRD.md`, `docs/ROADMAP.md`

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, uvicorn |
| ORM | SQLModel (wraps SQLAlchemy + Pydantic) |
| Database | SQLite (local), Alembic for migrations |
| Scheduler | APScheduler (AsyncIOScheduler) |
| AI | Claude API via Anthropic SDK (abstracted — see `backend/ai/`) |
| Notifications | python-telegram-bot |
| Scraping | Playwright + BeautifulSoup |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Code quality | Ruff, Black, Pytest |

---

## Project Structure

```
kiwi/
├── backend/
│   ├── api/v1/          # FastAPI route handlers — thin, no business logic
│   ├── ai/              # AI Provider abstraction (base.py + per-provider files)
│   ├── agents/          # Orchestration agents (BaseAgent → ScanAgent, future agents)
│   ├── scrapers/        # One file per job platform (BaseScraper interface)
│   ├── core/            # Shared business logic (matcher, deduplication, visa_tagger)
│   ├── database/        # SQLModel models, session, queries, Alembic migrations
│   ├── scheduler/       # APScheduler setup
│   ├── notifications/   # Telegram bot
│   ├── config/          # Settings loaded from .env via pydantic-settings
│   ├── logging_config.py
│   └── main.py          # FastAPI app entry point
├── frontend/
│   └── src/
│       ├── api/         # All fetch calls to FastAPI in one place
│       ├── components/  # Reusable UI components
│       ├── pages/       # Full page views
│       └── hooks/       # Custom React hooks
├── tests/backend/       # Pytest tests
├── scripts/setup.sh     # One-command local setup
├── logs/                # Runtime log files (gitignored)
├── docs/                # VISION.md, PRD.md, ROADMAP.md
├── .env                 # Secrets — never commit
├── .env.example         # Template — always commit
├── alembic.ini
├── pyproject.toml       # Ruff, Black, Pytest config
└── requirements.txt
```

---

## Key Architecture Rules

1. **API versioning**: All routes are mounted at `/api/v1/`. Never skip versioning.
2. **AI Provider abstraction**: All AI calls go through `backend/ai/base.py` (`AIProvider`). Never call the Anthropic SDK directly from routes or agents — always use `get_ai_provider()`.
3. **No authentication**: V1 is local-only, single-user. No auth middleware, no user table.
4. **Agent extensibility**: To add a new agent (Visa, Resume, Interview, Settlement), create `backend/agents/<name>_agent.py` extending `BaseAgent`, then register it in `main.py` lifespan. No structural changes needed.
5. **Scraper extensibility**: To add a new job source, create `backend/scrapers/<platform>.py` extending `BaseScraper`, then register it in `ScanAgent.run()`.
6. **No secrets in code**: All keys come from `.env` via `backend/config/settings.py`. Never hardcode.
7. **Structured logging**: Use named loggers (`scanner`, `telegram`, `application`). Errors go to `errors.log` automatically.

---

## Running Locally

```bash
# One-time setup
bash scripts/setup.sh

# Backend (from project root, venv activated)
uvicorn backend.main:app --reload

# Frontend (separate terminal)
cd frontend && npm run dev

# Dashboard
open http://localhost:5173

# API docs
open http://localhost:8000/docs
```

## Development Phase

Currently: **Phase 1 — Core Infrastructure** (scaffolding complete)

Next: Phase 2 — Job Scrapers
