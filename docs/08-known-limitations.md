# 08 — Known Limitations & Future Considerations

These are **limitations of the MVP scope or deployment posture**, not
security failures. The checkpoint documented here passed the final
independent security audit and targeted retest.

## 1. Product scope limitations

| Limitation | Detail |
|---|---|
| Drag-and-drop deferred | Status changes use an accessible `<select>` control. Drag-and-drop was explicitly deferred and is **not implemented** anywhere in code. |
| No native mobile application | Responsive web (desktop + tablet) only; no native/installed app exists. |
| No comment edit/delete/moderation | Comments are create/read only — no API, UI, or data model for editing, deleting, moderating, or reacting. |
| No status-transition restrictions | Any approved status can be set from any other by an authorized actor (by design). |
| No registration / recovery / MFA | Authentication is email+password login against pre-provisioned users only. |

## 2. Security-posture limitations

| Limitation | Detail | Consideration |
|---|---|---|
| Prototype/in-process rate limiter | `app/auth/rate_limit.py` keeps a fixed-window counter in process memory, keyed by (IP, email). It does not share state across workers/replicas and resets on restart. Disabled unless thresholds are configured. | Production must supply shared rate-limit infrastructure (e.g. Redis) or edge/proxy throttling; do not rely on this limiter. |
| Dummy-hash timing note | Unknown-email logins perform equivalent Argon2id work via a constant dummy hash; perfect timing equality is explicitly not claimed. | Acceptable for MVP; revisit if account-enumeration resistance needs strengthening. |
| No security headers in-app | The application sets no HSTS/CSP/etc. headers itself. | Apply headers at the reverse proxy / production layer (see 07). |
| Host-fallback origin posture | With no configured allowlist, Origin/Referer validation trusts only the request's own validated Host (plain-HTTP assumption). TLS-terminating deployments should configure the explicit allowlist. | Configure `CORS_ALLOWED_ORIGINS_RAW` in production. |

## 3. Deployment/tooling limitations

| Limitation | Detail |
|---|---|
| Local Docker frontend uses development tooling | `frontend/Dockerfile` runs `npm run dev` (`next dev`) with hot-reload mounts — appropriate locally only. Production must serve a built application and must not run `next dev`. |
| Production deployment configuration separate from local setup | `docker-compose.yml` documents and supports local development only. Production topology (reverse proxy, TLS, built frontend, ENVIRONMENT=production, explicit CORS allowlist, session lifetime policy) is a separate deployment effort that has not been performed as part of this MVP. |
| Session cleanup | Expired/revoked `auth_sessions` rows are not purged automatically; expired rows are simply never matched. | 

## 4. Accessibility observations carried from QA

Verified QA accessibility findings, deliberately **not** classified as
security failures:

- **Dialogs do not automatically move focus** to the dialog on open
  (task form, delete confirmation, comments panel render without an
  initial focus transfer).
- **Escape behavior is not consistent across dialogs:** the comments panel
  closes on Escape; the task create/edit form and delete confirmation do not
  implement Escape handling.

These are usability/accessibility improvements for future iterations.

## 5. Future considerations (not implemented)

Candidates raised by scope decisions above — none exist in code today:
drag-and-drop with keyboard-accessible alternatives; comment lifecycle
(edit/delete/moderation); shared rate-limit storage; production deployment
pipeline; session-table housekeeping; focus management and Escape consistency
in dialogs.
