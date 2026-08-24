# 05 — Authorization & RBAC

Role-based access control is enforced **backend-side** in a single module
(`backend/app/auth/authorization.py`); routes and services call these policies
before touching data. The frontend hides controls as a UX hint only — the
server is authoritative.

## 1. Roles

Exactly two approved roles exist, persisted in `users.role` with a DB CHECK
constraint: `"pm"` and `"developer"`. Any authenticated identity whose role
falls outside the approved set **fails closed**: every policy denies access.
There are no other roles and no anonymous capabilities beyond
`GET /api/health` and login.

## 2. Permission matrix

| Capability | PM | Developer | Enforcement |
|---|---|---|---|
| View tasks (list / single) | ✔ | ✔ | approved-role check |
| Create task | ✔ | ✖ 403 | `can_create_task` → PM required |
| Edit task fields (title/description/priority/due date) | ✔ | ✖ 403 | `can_update_task` → PM required |
| Assign / reassign / unassign | ✔ | ✖ 403 | `can_assign_task`; PATCH is PM-only |
| Delete task | ✔ | ✖ 403 | `can_delete_task` → PM required |
| Change status of any task | ✔ | — | PM branch of `can_update_task_status` |
| Change status of **own assigned task** | ✔ | ✔ | developer branch: `task.assignee_id == user.id`, both server-loaded |
| Change status of unassigned task | ✔ | ✖ 403 | developer branch denies null assignee |
| Change status of another developer's task | ✔ | ✖ 403 | ownership mismatch denied |
| Add comment on any task | ✔ | ✔ | `can_add_comment` |
| Read comments on any task | ✔ | ✔ | approved-role check |

Additional rules verified in source:

- A Developer sending a status-only payload to the general
  `PATCH /api/tasks/{task_id}` endpoint is still rejected (403) — the
  dedicated `/status` endpoint is their only mutation path.
- Status transitions are deliberately unrestricted: any approved status can be
  set from any other (`to_do → done` etc.). WHO may change status is policy;
  WHICH approved status is chosen is not restricted.
- Comments are not assignment-restricted: both roles may comment on any task.
- There are no comment edit/delete/moderation capabilities anywhere in code.

## 3. Identity & decision inputs

- Authentication (who you are; 401 when unknown) is performed by session
  dependencies before authorization runs. Authorization answers what you may
  do (403 when insufficient).
- Every decision uses **server-loaded data only**: the `User` row resolved from
  the session's `user_id`, and the `Task` row loaded by primary key. Client
  claims about role/id/ownership/assignment are never consulted.
- Comment authorship is always `authenticated_user.id`.
- Timestamps and identity fields are absent from request schemas entirely.

## 4. Error contract

| Condition | Result |
|---|---|
| No/unknown/expired/revoked session | **401** `{"detail": "Not authenticated"}` (generic) |
| Insufficient permission (any reason) | **403** `{"detail": "Forbidden"}` via central handler |
| Missing referenced object | **404** `{"detail": "Not found"}` |

Internal denial reasons (e.g. `pm_required`,
`developer_not_assigned_to_task`) never leave the server; the HTTP layer
emits only the generic body, so responses leak nothing about roles,
assignments, or object existence beyond success/failure.

## 5. Frontend reflection (UX hint only)

- PM sees: *+ New Task*, per-card *Edit*/*Delete* buttons, status `<select>` on all cards.
- Developer sees: status `<select>` **only** on cards where
  `task.assignee_id === current user id`; other cards render read-only status
  text — no mutation control is rendered at all.
- Unknown/unapproved client roles render view-only UIs (e.g. comments panel
  read-only), but this is cosmetic; the backend remains the gate.
