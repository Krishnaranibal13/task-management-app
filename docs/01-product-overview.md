# 01 — Product Overview

**Project:** Task Management MVP
**Historical validation checkpoint:** commit `2804f1b` — *fix: add origin referer csrf validation*. The product behavior documented below was originally validated at this checkpoint; the repository may contain later frontend and dependency-maintenance updates.
**Status:** Implemented and validated at this checkpoint (Development validation, independent QA / browser validation, final independent security audit, SEC-MED-01 correction, independent targeted security retest).

---

## 1. What this product is

A responsive web application (desktop + tablet) for a **small software team**
to manage work on a shared Kanban board. Two roles exist:

| Role | Capabilities |
|---|---|
| **Project Manager (PM)** | Create tasks · edit all task fields · delete tasks · assign/reassign · change priority · change status · change due date · add comments |
| **Developer** | View all tasks · add comments · update **only the status** of tasks **assigned to them** |

Developers explicitly cannot: create or delete tasks, reassign tasks,
modify title/description/priority/due date, or change another developer's
task or an unassigned task. This is enforced by backend authorization
(see [05-authorization-rbac.md](05-authorization-rbac.md)).

## 2. Task model

| Field | Required | Values / type | Notes |
|---|---|---|---|
| `title` | Yes | free text | |
| `description` | No | free text, nullable | |
| `assignee_id` | No | user id or null | null = unassigned; zero or one assignee |
| `priority` | Yes | `low`, `medium`, `high` | DB CHECK-constrained |
| `status` | Yes | `to_do`, `in_progress`, `review`, `done` | DB CHECK-constrained |

Statuses have **no transition restrictions** — any approved status may be set
from any other status (e.g. To Do → Done directly).

Due dates are optional calendar dates (`YYYY-MM-DD`). Timestamps
(`created_at`, `updated_at`) are server-managed and never client-settable.

## 3. Authentication

Email + password login only. There is no self-registration, password reset,
account management, or MFA in this MVP.

## 4. Interface

- Single-page Next.js application:
  - Login screen for unauthenticated visitors.
  - Authenticated view: identity header + logout, four-column Kanban board
    (To Do / In Progress / Review / Done), task create/edit form (PM),
    accessible delete confirmation (PM), comments dialog.
- Status is always changed via an **accessible `<select>` control** rendered
  for PMs on every task and for Developers **only on their own assigned
  tasks** (unauthorized cards show read-only status text).
- **Drag-and-drop was deferred and is NOT implemented.** It must not be
  described as a shipped feature anywhere.
- Comments: both roles may add comments on any task. Comment
  **edit/delete/moderation is NOT implemented** (no UI controls, no API).

## 5. Explicitly out of scope (not implemented)

- Drag-and-drop board interaction (deferred)
- Native mobile applications
- Comment editing, deletion, moderation
- Status transition rules/restrictions
- User registration / password reset / MFA
- Production-grade rate limiting (a local prototype limiter exists — see
  [08-known-limitations.md](08-known-limitations.md))

## 6. Where to read next

| Document | Contents |
|---|---|
| [02-architecture.md](02-architecture.md) | Runtime architecture, components, data flow diagram |
| [03-api-reference.md](03-api-reference.md) | Full endpoint reference |
| [04-authentication-security.md](04-authentication-security.md) | Sessions, cookies, CSRF, security controls |
| [05-authorization-rbac.md](05-authorization-rbac.md) | Role matrix, enforcement points |
| [06-testing-validation.md](06-testing-validation.md) | Test suites and validation evidence |
| [07-deployment-operations.md](07-deployment-operations.md) | Local dev vs production requirements |
| [08-known-limitations.md](08-known-limitations.md) | Known limitations and future considerations |
