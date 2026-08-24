# Task Management MVP

Web-based task management application for a small software team: Project
Managers plan, assign and track tasks on a four-column Kanban board;
Developers view work, comment, and update the status of tasks assigned to them.

**Status: MVP complete at commit `2804f1b`.** Validated per the approved
Development / QA / Security evidence (full backend regression, independent
QA/browser validation, final independent security audit — SEC-MED-01 corrected
and retested); see [docs/06-testing-validation.md](docs/06-testing-validation.md).

## Documentation

| Document | Contents |
|---|---|
| [docs/01-product-overview.md](docs/01-product-overview.md) | Product scope, roles, task model |
| [docs/02-architecture.md](docs/02-architecture.md) | Runtime architecture & data flow |
| [docs/03-api-reference.md](docs/03-api-reference.md) | Full API reference |
| [docs/04-authentication-security.md](docs/04-authentication-security.md) | Sessions, cookies, CSRF, security controls |
| [docs/05-authorization-rbac.md](docs/05-authorization-rbac.md) | PM/Developer permission matrix |
| [docs/06-testing-validation.md](docs/06-testing-validation.md) | Test suites & validation evidence |
| [docs/07-deployment-operations.md](docs/07-deployment-operations.md) | Local dev vs production requirements |
| [docs/08-known-limitations.md](docs/08-known-limitations.md) | Known limitations |

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router) · React 19 · TypeScript |
| Backend | FastAPI · SQLAlchemy 2 · Alembic (Python 3.11) |
| Database | MySQL 8 (InnoDB, utf8mb4) |
| Auth | Argon2id · server-side sessions · HttpOnly cookie · session-bound CSRF synchronizer token + Origin/Referer defense-in-depth |
| Infra | Docker Compose (local development stack) |

## Quick start (local development)

```bash
cp .env.example .env          # repo root; local-only placeholder credentials
docker compose up --build -d
```

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/api/health · OpenAPI docs: http://localhost:8000/docs
- MySQL: localhost:${MYSQL_HOST_PORT:-33061}

Backend without Docker:

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash (.venv/bin/activate elsewhere)
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env          # adjust values; never commit .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
cd backend && pytest          # full regression against the disposable taskdb_test database
```

DB-backed tests require the local MySQL container (`docker compose up -d db`);
they never touch the development database. Frontend suites live in
`frontend/tests/` (see docs/06 for details).

> **Note:** production topology is same-origin (frontend + API behind one
> reverse proxy, `ENVIRONMENT=production`, built Next.js output — never
> `next dev`). The compose file is strictly a local development convenience.
> See [docs/07-deployment-operations.md](docs/07-deployment-operations.md).

## Repository layout

```
task-management-app/
├── docs/                          # technical documentation package (entry point above)
├── frontend/                      # Next.js + TypeScript app (app/, lib/, tests/)
├── backend/
│   ├── app/
│   │   ├── main.py                # application factory, CORS/validation/403 handlers
│   │   ├── api/routes/            # users, tasks, comments, health routers
│   │   ├── auth/                  # login/sessions/CSRF/origin/RBAC/rate-limit
│   │   ├── core/config.py         # env-driven settings
│   │   ├── db/, models/, schemas/, services/
│   ├── migrations/                # Alembic environment + versions
│   ├── tests/                     # pytest suite (real MySQL)
│   └── Dockerfile
├── infrastructure/mysql/initdb/   # local test-database provisioning scripts
├── docker-compose.yml             # local dev stack: db + backend + frontend
└── README.md
```
