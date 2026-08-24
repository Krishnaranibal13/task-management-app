# 07 — Deployment & Operations

Local development setup and production requirements are deliberately
different things in this repository. Both are documented here; secrets are
referenced by **name only** — never values.

## 1. Local development (Docker Compose)

```bash
cp .env.example .env          # repo root; fill local-only placeholder credentials
docker compose up --build -d
```

| Service | URL (host) | Notes |
|---|---|---|
| Frontend | http://localhost:3000 | Next.js dev server (`npm run dev`) with hot reload |
| Backend | http://localhost:8000/api/health | Alembic `upgrade head` runs automatically before uvicorn starts |
| MySQL 8.4 | localhost:33061 → `db:3306` in-network | host port overridable via `MYSQL_HOST_PORT` |

Environment variables consumed locally (names and purpose):

| Variable | Purpose |
|---|---|
| `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD` | required by compose — no fallbacks |
| `MYSQL_DB`, `MYSQL_USER` | database/user names (defaults `taskdb` / `appuser`) |
| `MYSQL_HOST_PORT` | host-side published DB port |
| `ENVIRONMENT` | backend mode: `local` \| `development` \| `production` |
| `SESSION_LIFETIME_SECONDS` | positive integer; **required for any login** (sessions fail closed without it) |
| `CORS_ALLOWED_ORIGINS_RAW` | explicit trusted-origin allowlist (comma-separated) |
| `LOGIN_RATE_LIMIT_MAX_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | optional login throttle; disabled when unset |
| `SESSION_COOKIE_NAME` | cookie name (local default `session`) |
| `NEXT_PUBLIC_API_BASE_URL` | frontend → backend base URL |

Backend-local development without Docker: create `backend/.env` from
`backend/.env.example`, run migrations with `alembic upgrade head`, then
`uvicorn app.main:app --reload --port 8000`.

## 2. Production requirements

The following are **requirements/decisions for production deployment**, not
optional suggestions:

- **`ENVIRONMENT=production` must be set.** This is what enables the `Secure`
  cookie attribute; running production under `local`/`development` would ship
  a non-Secure session cookie.
- **A positive `SESSION_LIFETIME_SECONDS` is mandatory.** Session creation
  fails closed if the value is missing or non-positive.
- **Serve the built Next.js application** (`next build` + `next start` or an
  equivalent production server). Production **MUST NOT** run `next dev`.
- **Same-origin topology preferred:** serve the frontend and the API from one
  origin behind a reverse proxy. The local compose layout (separate ports,
  cross-origin calls, dev server) is a development convenience only.
- **If cross-origin is unavoidable,** set `CORS_ALLOWED_ORIGINS_RAW` to the
  explicit list of exact trusted origins. Credentialed wildcard CORS is
  prohibited by construction (the app refuses to start with `*` configured).
- **Production-grade rate limiting remains a deployment hardening item.**
  The built-in login limiter is an in-process fixed-window prototype that does
  not work across multiple workers/replicas; deploy shared infrastructure
  (e.g. Redis-based limiting) or an edge/proxy-level control instead of
  relying on it.
- **Security headers are not emitted by the application itself**; apply them
  at the reverse proxy / production serving layer (e.g. HSTS, CSP,
  X-Content-Type-Options). TLS termination belongs at this layer too — when
  TLS terminates at a proxy, configure the explicit origin allowlist so
  Origin checks match the public scheme/host.
- Secrets (database credentials, etc.) are supplied via environment only;
  never commit `.env` files.

## 3. Database operations

- Schema management is exclusively Alembic. Linear history:
  `2d80cdb002f4` (users/tasks/comments) → `29fac519f35f` (auth_sessions).
  Apply with `alembic upgrade head`; connection details come from environment
  settings, never from `alembic.ini`.
- Test databases (`taskdb_test`, `taskdb_migration_test`) are local-testing
  constructs provisioned by `infrastructure/mysql/initdb/03-local-test-databases.sql`;
  they have no role in production.

## 4. Runtime configuration summary

| Setting | Behavior when unset/misconfigured |
|---|---|
| `SESSION_LIFETIME_SECONDS` ≤ 0 or absent | Login fails closed (500 on session creation); no long-lived sessions invented |
| `CORS_ALLOWED_ORIGINS_RAW` empty | No CORS middleware registered; Origin/Referer validation falls back to strict same-host matching |
| Wildcard `*` present | Startup refusal (RuntimeError) |
| Rate-limit variables unset | Login throttle disabled entirely |
