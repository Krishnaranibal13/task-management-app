# 06 — Testing & Validation

## 1. Test layout (inspected read-only in the repository)

### Backend — `backend/tests/` (pytest, real MySQL)

Runs against the dedicated disposable database **`taskdb_test`**; destructive
Alembic round-trip tests run against **`taskdb_migration_test`**. The fixture
suite hard-refuses to purge any other database and never falls back to the
development database `taskdb`. Tests exercise real MySQL — SQLite results are
never used as MySQL evidence. DB-backed suites auto-skip with guidance when
MySQL is unreachable.

| Suite | Focus | Tests |
|---|---|---|
| `test_tasks_api.py` | Task API contracts, RBAC negatives, CSRF on tasks | 45 |
| `test_origin_referer_validation.py` | SEC-MED-01 Origin/Referer defense-in-depth + normalization guarantees | 24 |
| `test_authorization.py` / `test_authorization_http.py` | Policy unit + HTTP-level authorization | 23 + 10 |
| `test_comments_api.py` | Comment API, authorship, RBAC/CSRF/404 behavior | 22 |
| `test_auth_api.py` | Login/logout/me flows, generic failures, cookie contract | 17 |
| `test_auth_csrf_bootstrap.py` | `/api/auth/csrf` rotation semantics | 16 |
| `test_users_directory.py` | User directory endpoint | 16 |
| `test_db_integration.py` | Real-MySQL relationships, constraints, cascades | 13 |
| `test_auth_security.py` | Argon2id hashing, dummy-hash equivalence | 6 |
| `test_enums.py`, `test_models.py`, `test_schemas.py`, others | Domain values, models, strict schemas, health, logging hygiene, validation scope, DB isolation, migrations | remainder |

Total: **254 pytest tests collected and passed** in the approved final
regression (see §2).

### Frontend — `frontend/tests/`

- Unit-style suites (`node:test`): `auth.test.mjs` (290 lines),
  `tasks.test.mjs` (228), `comments.test.mjs` (209) — API-client behavior
  with mocked fetch plus source-contract assertions.
- Browser automation (`playwright-core` driving Chromium/system Edge):
  `browser-flows.mjs` (5A auth), `browser-flows-5b.mjs` (5B board),
  `browser-flows-5c.mjs` (5C comments) — login/logout, PM workflows,
  Developer status restrictions, comments, storage-security audit,
  sanitized error simulation.

Run commands (as supported by the repository):

```bash
cd backend && pytest                                   # backend suite (needs local MySQL)
cd frontend && node tests/auth.test.mjs                # example unit suite
node tests/browser-flows-5c.mjs                        # browser flow (needs running stack)
```

## 2. Final validation evidence at checkpoint `2804f1b`

Approved pipeline: Development validation → independent QA/browser validation →
final independent security audit → SEC-MED-01 correction → independent targeted
security retest. **Final security status: SECURITY PASSED.**

| Evidence | Result |
|---|---|
| Full backend regression after the SEC-MED-01 correction, on `taskdb_test` | **254 passed** |
| Independent targeted security retest (Origin/Referer focused, `test_origin_referer_validation.py`) | **24/24 passed** |
| Affected auth/CSRF regression (`test_auth_api.py` + `test_auth_csrf_bootstrap.py`) | **33/33 passed** |

These results are **approved validation evidence** from the Development /
independent QA / independent Security pipeline at this checkpoint. They are
documented here as received; they were **not re-executed as part of the
documentation phase**.

The independent QA phase previously validated: backend automated regression,
frontend unit suites, browser flows for PM workflows, Developer workflows
(including own-task-only status changes), comment workflows, authorization
negatives, CSRF negatives, error sanitization, keyboard accessibility,
responsive layouts (desktop/tablet), and browser-storage security behavior.

## 3. Coverage notes

- The Origin/Referer suite (24 test functions, verified directly in
  `tests/test_origin_referer_validation.py`) covers: trusted/untrusted Origin,
  trusted/untrusted Referer fallback, malformed presentation, missing-CSRF and
  invalid-CSRF rejection remaining intact, protection of every mutating
  endpoint (logout, task create/update/status/delete, comment create,
  developer `/status`), safety of GET endpoints, absence of credentials/tokens
  in logs or error bodies, exact matching (no substring/suffix),
  scheme/port sensitivity, default-port equivalence, Origin-over-Referer
  precedence, opaque `null` rejection, and the validated same-origin Host fallback.
- No coverage numbers (percentages) are claimed anywhere — only pass counts.

## 4. Reproducing locally

Prerequisites: Docker stack running (`docker compose up -d db` is sufficient
for backend tests; the init script
`infrastructure/mysql/initdb/03-local-test-databases.sql` provisions the two
test schemas idempotently).

```bash
cd backend
source .venv/Scripts/activate        # Windows Git Bash (.venv/bin/activate elsewhere)
pip install -r requirements.txt -r requirements-dev.txt
pytest
```
