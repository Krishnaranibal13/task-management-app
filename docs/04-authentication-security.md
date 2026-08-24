# 04 — Authentication & Security

All controls below were inspected in source at commit `2804f1b` and are
covered by the automated suites described in
[06-testing-validation.md](06-testing-validation.md).

## 1. Password authentication

| Control | Implementation (verified) |
|---|---|
| Hashing | **Argon2id** via `argon2-cffi` (established library, default parameters — no custom cryptography). `backend/app/auth/security.py` |
| Generic failure | Unknown email and wrong password both return the identical generic **401** `"Invalid email or password"`. No account-existence signal is returned or logged. |
| Equivalent work | Unknown-email attempts verify against a constant **dummy hash** so a fast-path timing difference for non-existent accounts is avoided. (Perfect timing equality is explicitly *not* claimed.) |
| Hash handling | Hashes are never logged and never returned by any API; the response schema has no field for them. |

Login rate limiting exists as an optional, configuration-driven throttle
(HTTP 429) but is an **in-process prototype** — see
[08-known-limitations.md](08-known-limitations.md).

## 2. Sessions

Server-side, stateful sessions stored in the `auth_sessions` MySQL table
(infrastructure table, separate from domain models):

- Credential: `secrets.token_urlsafe(32)` (~256 bits entropy), delivered to the
  browser **only** as an HttpOnly cookie. It never appears in JSON responses,
  URLs, or logs.
- **Digest-only persistence:** only SHA-256 hex digests of the session token
  and CSRF token are stored. A database read cannot be replayed as a session.
- Lookup is by digest with `revoked_at IS NULL AND expires_at > now()` —
  missing, unknown, expired and revoked sessions all reduce to the same
  generic **401**.
- Expiry derives from the configured `SESSION_LIFETIME_SECONDS`, which is
  **required and positive-or-nothing**: creation fails closed if unset or
  non-positive. Cookie Max-Age uses the same value.
- Logout (`POST /api/auth/logout`) revokes server-side (sets `revoked_at`)
  before responding — authoritative invalidation, not just cookie clearing.
- The frontend treats server revocation as authoritative: on network/5xx
  logout failures it keeps the user "logged in" rather than faking success.

## 3. Session cookie

| Attribute | Value |
|---|---|
| Name | configurable (`SESSION_COOKIE_NAME`; local default `session`) |
| HttpOnly | always — not readable by JavaScript |
| SameSite | `Lax` |
| Path | `/` |
| Secure | enabled when `ENVIRONMENT=production` |

## 4. CSRF protection

Two layers, applied uniformly to every authenticated mutating endpoint via a
single dependency (`require_csrf`):

1. **Origin/Referer defense-in-depth (SEC-MED-01)** — runs first:
   - Applies to POST/PUT/PATCH/DELETE only; safe methods unaffected.
   - If `Origin` is present it must exactly match the trusted-origin set;
     otherwise a present `Referer` must have its origin component match.
   - Matching is **exact equality on normalized origins** (lowercased
     scheme/host, effective port, default ports elided). No wildcards,
     substrings, suffixes, or regex. Opaque `null` origins are rejected.
     Userinfo, comma lists, whitespace, malformed ports, unexpected path/query
     components → malformed → **403**.
   - Trusted origins come from the single authoritative CORS allowlist
     (`CORS_ALLOWED_ORIGINS_RAW`). When no allowlist is configured
     (same-origin posture), the request's own strictly validated `Host`
     header defines the only acceptable self-origin; an invalid Host fails
     closed with the same generic 403.
   - Absence of both headers is permitted (same-origin browsers may omit
     them); the synchronizer token below remains the primary control.
   - Full Referer URLs are never stored, echoed, or logged.
2. **Session-bound synchronizer token (primary):**
   - Issued at login and rotated by `GET /api/auth/csrf`; only its SHA-256
     digest persists server-side.
   - Presented via the `X-CSRF-Token` header; compared to the session-bound
     digest using constant-time comparison. Missing / invalid /
     foreign-session tokens → **403**.
   - Rotation invalidates the previous raw token for that session immediately
     (multi-tab refresh handled by re-bootstrapping from `/api/auth/csrf`).
   - Tokens are never logged.

## 5. Authorization (summary)

Backend-enforced RBAC only — see
[05-authorization-rbac.md](05-authorization-rbac.md) for the full matrix:

- Decisions derive exclusively from the server-loaded user and task rows.
- Identity, role, comment authorship, timestamps and session state are never
  client-settable; those fields do not exist in any request schema (supplying
  them is an unknown-field 400).
- IDOR/BOLA defense: object access is resolved through authorization checks on
  server-loaded objects; developers cannot act on tasks they are not assigned
  to even when they supply valid ids.

## 6. Input handling

- All request schemas inherit `StrictModel` (`extra="forbid"`).
- Undeclared fields on mutating methods → HTTP **400** (centralized handler);
  other validation failures → HTTP **422**. Both return sanitized bodies:
  field locations plus a generic `invalid_input` label only — Pydantic's raw
  errors embed submitted values (e.g. passwords) and are never echoed.
- Enum fields accept only approved values; DB CHECK constraints enforce the
  same sets at storage level.

## 7. Frontend security behavior

Verified by reading all frontend code (`frontend/lib`, `frontend/app`) and by
the QA storage audit:

- The only credential is the backend-issued HttpOnly cookie; every request
  uses `credentials: "include"`.
- The raw CSRF token lives **only** in runtime memory (a React ref). There is
  no use of `localStorage`, `sessionStorage`, IndexedDB, or `document.cookie`
  anywhere in the application code (grep-verified).
- Errors surface as sanitized generic messages mapped from HTTP status codes;
  passwords/tokens/header values are never logged.
- On any 401 the client resets in-memory state and shows the login screen.

## 8. Logging rules

Security events (`auth_failure`, `auth_success`, `logout`, `csrf_bootstrap`)
log event names and non-sensitive facts only. Never logged: passwords, hashes,
session identifiers/tokens, cookies, CSRF tokens, request/response bodies,
emails, or header values. Startup logs print environment name, MySQL host/port
and database name — never credentials.

## 9. CORS

- Explicit allowlist via `CORS_ALLOWED_ORIGINS_RAW` (comma-separated).
- Credentialed wildcard CORS is prohibited **by construction**: the app raises
  a startup error if `*` appears while credentials are allowed.
- Same-origin deployment is the preferred production posture; if cross-origin
  is required, origins must be listed explicitly.

## 10. Not implemented (do not assume)

No MFA, no password reset/recovery, no registration endpoint, no account
management API, no shared/distributed rate limiting, no security-header
injection inside the app (headers may be added at a reverse proxy — see
[07-deployment-operations.md](07-deployment-operations.md)).
