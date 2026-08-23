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

  return (
    <section className="card" aria-labelledby="shell-heading">
      <header className="shell-header">
        <div>
          <h1 id="shell-heading">Task Management MVP</h1>
          <p className="subtitle">Signed in</p>
        </div>
        <button
          type="button"
          className="primary"
          onClick={() => void handleLogout()}
          disabled={loggingOut}
        >
          {loggingOut ? "Logging out…" : "Log out"}
        </button>
      </header>

      {logoutError !== null && (
        <p className="form-error" role="alert">
          {logoutError}
        </p>
      )}

      <dl className="whoami">
        <div className="stackRow">
          <dt>Email</dt>
          <dd>{user?.email}</dd>
        </div>
        <div className="stackRow">
          <dt>Role</dt>
          <dd>{user ? (ROLE_LABELS[user.role] ?? user.role) : ""}</dd>
        </div>
      </dl>

      <div className="placeholder" aria-label="Tasks placeholder">
        <p>Task workspace</p>
        <p className="muted">
          The task board will appear here in an upcoming phase.
        </p>
      </div>
    </section>
  );
}
