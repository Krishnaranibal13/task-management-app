# 03 — API Reference

Base URL (local compose): `http://localhost:8000`. All request and response
bodies are JSON. Originally verified against source at commit `2804f1b`. Later frontend and dependency-maintenance updates do not change the API contract unless explicitly documented.
(`backend/app/main.py`, `backend/app/auth/routes.py`, `backend/app/api/routes/*`).

## Conventions applying to every endpoint

| Aspect | Contract |
|---|---|
| Authentication | All `/api/*` endpoints except `GET /api/health` require a valid session cookie. Missing / unknown / expired / revoked sessions all return **401** `{"detail": "Not authenticated"}` — indistinguishable by design. |
| CSRF | Every mutating endpoint (`POST`/`PATCH`/`DELETE`) requires header **`X-CSRF-Token`** bound to the session. Missing/invalid/foreign token → **403** `{"detail": "CSRF validation failed"}`. Origin/Referer defense-in-depth also applies to mutations (untrusted/malformed presentation → 403). Safe methods (`GET`) never require CSRF. |
| Authorization | Role rules enforced backend-side after authentication. Insufficient permission → **403** `{"detail": "Forbidden"}` (generic; no reason strings or identifiers leaked). |
| Unknown fields | Undeclared fields on mutating requests → **400** with locations only: `{"detail":[{"loc":[...],"error":"invalid_input"}]}`. Other validation failures (missing/wrong-typed values) → **422**, same sanitized shape. Submitted input values are never echoed. |
| Not found | Non-existent task referenced in a path → **404** `{"detail": "Not found"}`. |

---

## Health

### GET /api/health
Public liveness probe. No auth, no CSRF.

**Response** `200`: `{"status": "ok"}`

---

## Authentication

### POST /api/auth/login
Authenticate with email + password and create a session.

- Auth required: no · CSRF: no (session does not exist yet)
- Rate limit: optional configured login throttle may return **429** `{"detail": "Too many attempts"}` when enabled (disabled unless thresholds are configured).

**Request body**

| Field | Type | Required |
|---|---|---|
| `email` | string | yes |
| `password` | string | yes |

Unknown extra fields → 400.

**Behavior**
- Email lookup is case-insensitive-normalized (`strip().lower()`).
- Unknown email performs equivalent Argon2id verification work against a
  constant dummy hash, then fails identically to a wrong password.
- Success creates a server-side session row (digest-only persistence) and sets
  the HttpOnly session cookie. **The session credential is never returned in
  the JSON body.**

**Responses**
- `200`: `{"csrf_token": "<raw synchronizer token>", "token_type": "session_cookie"}` + `Set-Cookie` (HttpOnly; `SameSite=Lax`; `Path=/`; `Secure` in production; Max-Age = configured lifetime).
- `401`: `{"detail": "Invalid email or password"}` — identical for unknown email and wrong password.
- `400`/`422`: validation, per conventions.
- `500` if `SESSION_LIFETIME_SECONDS` is unset/non-positive (sessions fail closed).

### POST /api/auth/logout
Revoke the current server-side session authoritatively and clear the cookie.

- Auth required: yes · CSRF: **required**

**Responses**
- `200`: `{"detail": "Logged out"}`; cookie deleted with matching attributes.
- `401` unauthenticated; `403` missing/invalid CSRF or untrusted origin.

Revocation happens server-side before the response; a revoked session is
immediately unusable everywhere.

### GET /api/auth/me
Identity probe for the authenticated session. No CSRF (safe method).

**Response** `200`: `{"user_id": int, "email": string, "role": "pm"|"developer"}`

No sensitive values are included.

### GET /api/auth/csrf
CSRF bootstrap/rotation for an **existing active session** (used after SPA
refresh when the cookie survived but in-memory CSRF state was lost).

- Auth required: yes · CSRF: not required (safe bootstrap endpoint)

**Behavior**
- Generates a fresh cryptographically random token, replaces **only this
  session's** stored CSRF digest. The previously issued token for this session
  becomes invalid immediately. Session identity, creation time and expiry are
  untouched (no lifetime extension). Other sessions are unaffected.
- Response is marked non-cacheable (`Cache-Control: no-store`, `Pragma: no-cache`).
- The raw token is returned exactly once and never logged or persisted raw.

**Responses**
- `200`: `{"csrf_token": "<fresh raw token>"}`
- `401` when there is no valid session.

---

## Users

### GET /api/users
Read-only directory of users (assignee picker / comment attribution).

- Roles: `pm`, `developer` · CSRF: none (safe read)

**Response** `200`: array of `{"id": int, "email": string, "role": "pm"|"developer"}`
— exactly these fields; password hashes/timestamps/security state are structurally excluded.

---

## Tasks

Task status values: `to_do` · `in_progress` · `review` · `done`.
Priority values: `low` · `medium` · `high`.

### GET /api/tasks
List all tasks. Roles: `pm`, `developer`. No CSRF.

**Response** `200`: array of task objects:

```json
{
  "id": 1,
  "title": "Ship checkout flow",
  "description": null,
  "assignee_id": 2,
  "priority": "high",
  "status": "to_do",
  "due_date": "2026-09-01"
}
```

(`description`, `assignee_id`, `due_date` nullable.)

### GET /api/tasks/{task_id}
Fetch one task. Roles: `pm`, `developer`. No CSRF.

**Responses:** `200` task object · `404` if missing.

### POST /api/tasks — *PM only*
Create a task.

- Roles: `pm` only (developer/unapproved → 403) · CSRF: **required**

**Request body**

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | string | yes | |
| `description` | string \| null | no | default null |
| `assignee_id` | int \| null | no | must reference an existing user when non-null, else **400** `{"detail": "Invalid assignee"}` |
| `priority` | enum | yes | |
| `status` | enum | yes | |
| `due_date` | date `YYYY-MM-DD` \| null | no | |

Server-managed fields (`id`, `created_at`, `updated_at`) are not accepted → 400.

**Responses:** `201` created task object · `400` invalid assignee / unknown field · `403` non-PM · `422` missing/invalid required values.

### PATCH /api/tasks/{task_id} — *PM only*
General partial edit: title, description, assignee, priority, status, due date.

- Roles: `pm` only · CSRF: **required**

**Semantics**
- True partial PATCH: omitted fields remain unchanged; empty body `{}` allowed (no-op).
- Nullable fields (`description`, `assignee_id`, `due_date`) may be explicitly
  `null` — `assignee_id: null` unassigns.
- Required fields (`title`, `priority`, `status`) must **not** be explicitly
  null (→ 422 before any database involvement).
- Developers are rejected by policy even for a status-only payload — their only
  mutation path is the dedicated `/status` endpoint below.

**Responses:** `200` updated task · `400` invalid assignee / unknown field · `403` non-PM · `404` missing task.

### PATCH /api/tasks/{task_id}/status — *PM always; Developer on own assigned tasks only*
Change task status. Body is **exactly** `{"status": <enum>}` (anything else → 400/422).

- CSRF: **required**

**Authorization rule** (server-loaded data only): PM may change any task;
a developer may change status only where `task.assignee_id == authenticated user.id`.
Developers on unassigned or other developers' tasks → 403.
No transition restrictions exist between approved statuses.

**Responses:** `200` updated task · `403` unauthorized role/ownership or CSRF failure · `404` missing task.

### DELETE /api/tasks/{task_id} — *PM only*
Delete a task permanently (its comments cascade at DB level; no soft delete).

- Roles: `pm` only · CSRF: **required**

**Responses:** `204` no content · `403` non-PM / CSRF failure · `404` missing task.

---

## Comments

Both roles may read and create comments on any existing task.
There are **no** update/delete/moderation endpoints by design.

### GET /api/tasks/{task_id}/comments
Roles: `pm`, `developer`. No CSRF.

**Response** `200`: array of:

```json
{
  "id": 10,
  "task_id": 1,
  "user_id": 2,
  "content": "Blocked by the API migration",
  "created_at": "2026-08-24T12:34:56"
}
```

Ordered by `created_at`, then `id`.

### POST /api/tasks/{task_id}/comments
Roles: `pm`, `developer` (regardless of assignment) · CSRF: **required**

**Request body:** exactly `{"content": string}` — content required; explicit
null → 422; identity fields (`id`, `task_id`, `user_id`, `author_id`,
`created_at`, `role`) are not accepted → 400. The author is always derived
from the authenticated session server-side.

**Responses:** `201` created comment · `403` CSRF failure · `404` parent task missing · `422` missing content.

---

## Endpoint summary

| Method & path | Auth | CSRF | PM | Developer |
|---|---|---|---|---|
| `GET /api/health` | – | – | ✔ public | ✔ public |
| `POST /api/auth/login` | – | – | ✔ | ✔ |
| `POST /api/auth/logout` | ✔ | ✔ | ✔ | ✔ |
| `GET /api/auth/me` | ✔ | – | ✔ | ✔ |
| `GET /api/auth/csrf` | ✔ | – | ✔ | ✔ |
| `GET /api/users` | ✔ | – | ✔ | ✔ |
| `GET /api/tasks` | ✔ | – | ✔ | ✔ |
| `GET /api/tasks/{task_id}` | ✔ | – | ✔ | ✔ |
| `POST /api/tasks` | ✔ | ✔ | ✔ | ✖ 403 |
| `PATCH /api/tasks/{task_id}` | ✔ | ✔ | ✔ | ✖ 403 |
| `PATCH /api/tasks/{task_id}/status` | ✔ | ✔ | ✔ any task | ✔ own assigned only |
| `DELETE /api/tasks/{task_id}` | ✔ | ✔ | ✔ | ✖ 403 |
| `GET /api/tasks/{task_id}/comments` | ✔ | – | ✔ | ✔ |
| `POST /api/tasks/{task_id}/comments` | ✔ | ✔ | ✔ | ✔ |

OpenAPI docs are available from the running backend at `/docs`
(Swagger UI generated by FastAPI).
