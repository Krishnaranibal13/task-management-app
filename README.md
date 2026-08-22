# Task Management MVP — Foundation (Phase 1)

Web-based task management application for Project Managers and Developers.

**Current status: Phase 1 — project foundation only.**
Authentication, RBAC, task/comment features, and the Kanban board are
deliberately **not implemented yet**; they arrive in later phases per the
approved architecture.

## Approved stack

| Layer     | Technology              |
|-----------|-------------------------|
| Frontend  | Next.js 15 + TypeScript |
| Backend   | FastAPI (Python 3.11)   |
| Database  | MySQL 8                 |
| Testing   | pytest (+ Playwright later) |
| Infra     | Docker Compose, GitHub  |

## Repository layout

```
task-management-app/
├── frontend/                     # Next.js + TypeScript app
│   ├── app/                      # App Router pages/layouts/styles
│   ├── Dockerfile                # local dev image
│   └── .env.example              # safe env template
├── backend/                      # FastAPI service
│   ├── app/
│   │   ├── main.py               # application factory (/api/health, /api/meta)
│   │   ├── core/config.py        # env-driven settings (pydantic-settings)
│   │   ├── db/                   # engine/session/base scaffolding (MySQL)
│   │   ├── api/routes/           # health + meta routers only
│   │   ├── models/               # empty until Phase 2 (domain models)
│   │   └── schemas/              # empty until Phase 2 (request schemas)
│   ├── migrations/               # Alembic environment + versions/
│   ├── alembic.ini
│   ├── requirements.txt          # pinned dependencies
│   ├── tests/                    # pytest smoke tests
│   ├── Dockerfile
│   └── .env.example
├── infrastructure/mysql/initdb/  # optional MySQL init mount (schema stays in Alembic)
├── docker-compose.yml            # db + backend + frontend local stack
└── README.md
```

## Prerequisites

- Node.js ≥ 20 and npm (developed with Node 24)
- Python 3.11+
- Docker Desktop (optional, for the containerized local stack)
- A running MySQL 8 instance if not using Docker

## Local development — backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash (.venv/bin/activate on Linux/macOS)
pip install -r requirements.txt

cp .env.example .env               # adjust values; never commit .env
uvicorn app.main:app --reload --port 8000
```

- Health check: http://localhost:8000/api/health
- Metadata: http://localhost:8000/api/meta
- OpenAPI docs: http://localhost:8000/docs

### Database migrations (Alembic)

Migrations are wired but contain no revisions yet — the first revision is
authored in Phase 2 when domain models exist. With MySQL reachable:

```bash
cd backend
alembic upgrade head        # apply migrations
alembic revision --autogenerate -m "message"   # create a new revision (Phase 2+)
```

The connection URL is injected from `.env` via `app.core.config` — it is
never stored in `alembic.ini`.

## Local development — frontend

```bash
cd frontend
npm install
cp .env.example .env.local       # points at http://localhost:8000 by default
npm run dev
```

Open http://localhost:3000 — you should see the foundation placeholder page.

## Tests (backend)

```bash
cd backend
source .venv/Scripts/activate
pytest
```

Phase 1 tests cover `/api/health`, `/api/meta`, and unknown-route 404s.
Playwright end-to-end tests are introduced with the UI phases.

## Docker-based local stack

```bash
cp backend/.env.example backend/.env   # required: compose reads backend/.env
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend:  http://localhost:8000/api/health
- MySQL:    localhost:3306 (database `taskdb`, user `appuser`)

All schema changes go through Alembic (`alembic upgrade head` runs
automatically before backend startup in compose).

> Note: production topology is same-origin (frontend + API behind one
> reverse proxy). This compose file is strictly a local development
> convenience.

## Security posture (Phase 1)

No authentication exists yet, so no secrets are handled beyond local
placeholder DB credentials in uncommitted `.env` files. Later-phase
requirements (Argon2id, server-side sessions, CSRF synchronizer tokens,
strict input allowlists, security logging rules) are already reflected in
the settings scaffold so they are configuration-driven, not hardcoded.
