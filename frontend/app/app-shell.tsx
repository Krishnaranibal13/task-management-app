"use client";

/**
 * Minimal authenticated application shell (Phase 5A).
 *
 * Contains ONLY: app name, user email, role label, logout, and a
 * placeholder for the upcoming Task UI. Task/Kanban/Comment features
 * arrive in later phases. Role label is a UX hint only — backend
 * authorization remains authoritative.
 *
 * Logout failure handling: the backend session revocation is
 * authoritative. If it fails (network/server error), the user REMAINS
 * logged in and a sanitized, accessible error is announced — the UI
 * never fakes a logout that did not happen. The button stays usable so
 * the user can simply retry.
 */

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";

const ROLE_LABELS: Record<string, string> = {
  pm: "Project Manager",
  developer: "Developer",
};

const GENERIC_LOGOUT_ERROR = "Unable to log out. Please try again.";

export default function AppShell() {
  const { user, logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  async function handleLogout() {
    if (loggingOut) return;
    setLogoutError(null);
    setLoggingOut(true);
    try {
      await logout();
      // Success → AuthProvider cleared state; login UI renders next.
    } catch {
      // Sanitized only: no error object details (they may embed request
      // or network specifics). State intentionally NOT cleared.
      setLogoutError(GENERIC_LOGOUT_ERROR);
    } finally {
      setLoggingOut(false);
    }
  }

  const role = user?.role;
  const roleLabel = role ? (ROLE_LABELS[role] ?? role) : "";
  const roleBadgeClass = role === "pm"
    ? "role-badge role-badge--pm"
    : role === "developer"
    ? "role-badge role-badge--developer"
    : "role-badge role-badge--unknown";

  return (
    <>
      <header className="appbar" role="banner">
        <div className="appbar-left">
          <div className="appbar-logo" aria-hidden="true">
            <div className="appbar-logo-mark">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M9 11l3 3L22 4" />
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
              </svg>
            </div>
            <span className="appbar-wordmark">Task Management MVP</span>
          </div>
        </div>
        <div className="appbar-right">
          <span className="appbar-email" title={user?.email ?? ""}>
            {user?.email ?? ""}
          </span>
          <span className={roleBadgeClass}>{roleLabel}</span>
          <span className="appbar-divider" aria-hidden="true" />
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => void handleLogout()}
            disabled={loggingOut}
            aria-busy={loggingOut}
          >
            {loggingOut ? "Logging out…" : "Log out"}
          </button>
        </div>
      </header>
      {logoutError !== null && (
        <div className="error-banner" role="alert" style={{ margin: "0 var(--space-5) var(--space-4)" }}>
          <span className="error-banner-message">{logoutError}</span>
        </div>
      )}
      <main className="page-content" style={{ padding: "0 var(--space-5) var(--space-5)" }}>
        {logoutError === null ? null : null}
      </main>
    </>
  );
}