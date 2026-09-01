"use client";

/**
 * Root page: renders login UI or the authenticated shell based on the
 * centralized auth state. A "loading" splash avoids redirect loops and
 * prevents flashing the login form during session bootstrap.
 */

import LoginForm from "./login-form";
import AppShell from "./app-shell";
import TaskBoard from "./task-board";
import { useAuth } from "@/lib/auth-context";

export default function Home() {
  const { status, user } = useAuth();

  return (
    <div className="page">
      <main className="main">
        {status === "loading" && (
          <section className="login-card" aria-live="polite" aria-busy="true" style={{ margin: "auto", marginTop: "calc(50vh - 150px)", textAlign: "center" }}>
            <div className="appbar-logo" style={{ justifyContent: "center", marginBottom: "var(--space-4)" }} aria-hidden="true">
              <div className="appbar-logo-mark">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M9 11l3 3L22 4" />
                  <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                </svg>
              </div>
              <h1 className="login-title">Task Management MVP</h1>
            </div>
            <p className="subtitle">Checking your session…</p>
          </section>
        )}

        {status === "unauthenticated" && (
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", padding: "var(--space-4)" }}>
            <LoginForm />
          </div>
        )}

        {status === "authenticated" && user !== null && (
          <>
            <AppShell />
            <TaskBoard />
          </>
        )}
      </main>
    </div>
  );
}