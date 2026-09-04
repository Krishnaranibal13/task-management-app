"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";

const ROLE_LABELS: Record<string, string> = {
  pm: "Project Manager",
  developer: "Developer",
};

const GENERIC_LOGOUT_ERROR = "Unable to log out. Please try again.";
const THEME_KEY = "tm-theme";

type Theme = "light" | "dark";

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    </span>
  );
}

function TasksIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M8 9h8M8 13h5" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
      <path d="M16 17l5-5-5-5M21 12H9" />
    </svg>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    setTheme(
      document.documentElement.dataset.theme === "dark" ? "dark" : "light",
    );
  }, []);

  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    setTheme(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // Theme persistence is optional.
    }
  }

  async function handleLogout() {
    if (loggingOut) return;
    setLogoutError(null);
    setLoggingOut(true);
    try {
      await logout();
    } catch {
      setLogoutError(GENERIC_LOGOUT_ERROR);
    } finally {
      setLoggingOut(false);
    }
  }

  const role = user?.role;
  const roleLabel = role ? (ROLE_LABELS[role] ?? role) : "";
  const roleBadgeClass =
    role === "pm"
      ? "role-badge role-badge--pm"
      : role === "developer"
        ? "role-badge role-badge--developer"
        : "role-badge role-badge--unknown";

  const email = user?.email ?? "";
  const avatarLabel = email ? email.slice(0, 2).toUpperCase() : "TM";

  return (
    <div className="application-shell">
      <aside className="sidebar" aria-label="Application navigation">
        <div>
          <div className="sidebar-brand">
            <BrandMark />
            <div>
              <span className="sidebar-brand-title">Task Management</span>
              <span className="sidebar-brand-subtitle">Workspace</span>
            </div>
          </div>

          <nav className="sidebar-nav">
            <p className="sidebar-section-label">Workspace</p>
            <div className="sidebar-link sidebar-link--active" aria-current="page">
              <span className="sidebar-link-icon"><TasksIcon /></span>
              <span>Tasks</span>
            </div>
          </nav>
        </div>

        <div className="sidebar-bottom">
          <div className="sidebar-user">
            <span className="user-avatar" aria-hidden="true">{avatarLabel}</span>
            <div className="sidebar-user-copy">
              <span className="sidebar-user-email" title={email}>{email}</span>
              <span className="sidebar-user-role">{roleLabel}</span>
            </div>
          </div>

          <button
            type="button"
            className="sidebar-action"
            onClick={() => void handleLogout()}
            disabled={loggingOut}
            aria-busy={loggingOut}
          >
            <span className="sidebar-link-icon"><LogoutIcon /></span>
            <span>{loggingOut ? "Logging out…" : "Log out"}</span>
          </button>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <p className="topbar-eyebrow">Workspace</p>
            <h1 className="topbar-title">Tasks</h1>
          </div>

          <div className="topbar-actions">
            <button
              type="button"
              className="theme-toggle"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            </button>
            <span className={roleBadgeClass}>{roleLabel}</span>
          </div>
        </header>

        {logoutError !== null && (
          <div className="shell-alert" role="alert">
            <span>{logoutError}</span>
            <button type="button" className="btn btn-secondary" onClick={() => void handleLogout()} disabled={loggingOut}>
              Retry
            </button>
          </div>
        )}

        <main className="workspace-content">{children}</main>
      </div>
    </div>
  );
}
