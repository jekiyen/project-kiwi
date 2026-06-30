# Project Kiwi

> Personal AI migration copilot for relocating to New Zealand.

Project Kiwi automates the most time-consuming parts of the migration journey. It starts by discovering and ranking blue-collar job opportunities across multiple New Zealand platforms, evaluating each one against visa eligibility and personal fit — then grows over time into a complete relocation assistant.

**This is a single-user personal tool, not a public product.**

---

## Current Status

**Phase 0 — Foundation complete. Tech stack selection in progress.**

No application code has been written yet. See [docs/ROADMAP.md](docs/ROADMAP.md) for the full development plan.

---

## V1 Scope

| Capability | Status |
|------------|--------|
| Job discovery (6 NZ platforms) | Planned |
| AI ranking and match explanation | Planned |
| Visa eligibility tagging | Planned |
| Web dashboard (local) | Planned |
| Telegram notifications | Planned |
| Manual application tracking | Planned |
| 6-hour auto-scan + manual trigger | Planned |

---

## Target Roles

| Priority | Roles |
|----------|-------|
| P1 | Packhouse Worker, Fruit Picker, Orchard Worker, Farm Worker |
| P2 | Warehouse Worker, Manufacturing Worker, Factory Worker |
| P3 | Construction Labourer, General Labourer |

---

## Job Sources

- SEEK New Zealand
- Trade Me Jobs
- PickNZ
- Backpacker Board New Zealand
- Seasonal Jobs New Zealand
- Indeed New Zealand

---

## Tech Stack

> TBD — awaiting stack decision after Phase 0.

| Layer | Technology |
|-------|------------|
| Backend | TBD |
| Frontend / Dashboard | TBD |
| Database | TBD |
| Scheduler | TBD |
| AI | Claude API (Anthropic) |
| Notifications | Telegram |
| Runtime | Local macOS → VPS-ready |

---

## Folder Structure

> Will be updated once tech stack is finalized.

```
kiwi/
├── docs/
│   ├── VISION.md          # Product vision and long-term goals
│   ├── PRD.md             # Full product requirements
│   └── ROADMAP.md         # Development phases and milestones
├── README.md
└── CLAUDE.md              # Instructions for Claude Code
```

---

## Setup Instructions

> To be completed after tech stack is finalized in Phase 0.

### Prerequisites

- macOS
- Claude API key — [console.anthropic.com](https://console.anthropic.com)
- Telegram account (bot to be created via BotFather — see docs/TELEGRAM_SETUP.md)
- Additional dependencies TBD

### Installation

```bash
# TBD after stack decision
```

### Environment Variables

```bash
# .env (copy from .env.example)
CLAUDE_API_KEY=your_anthropic_api_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_personal_chat_id
```

### Running the System

```bash
# TBD after stack decision
```

---

## Development Workflow

1. All development is driven by Claude Code.
2. Document decisions before implementing them.
3. Complete and stabilize each phase before starting the next.
4. Update this README as the stack and folder structure evolve.
5. Resume changes are never applied automatically — always require approval.

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/VISION.md](docs/VISION.md) | Product vision, long-term goals, success metrics |
| [docs/PRD.md](docs/PRD.md) | Full product requirements, features, risks |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Development phases, deliverables, milestones |

---

## License

Private — personal use only.
# project-kiwi
