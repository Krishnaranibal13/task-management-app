"use client";

import LoginForm from "./login-form";
import AppShell from "./app-shell";
import TaskBoard from "./task-board";
import { useAuth } from "@/lib/auth-context";

export default function Home() {
  const { status, user } = useAuth();

  if (status === "loading") {
    return (
      <div className="loading-screen" aria-live="polite" aria-busy="true">
        <div className="loading-card">
          <span className="brand-mark brand-mark--large" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 11l3 3L22 4" />
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
          </span>
          <p>Checking your session…</p>
        </div>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <LoginForm />;
  }

  if (status === "authenticated" && user !== null) {
    return (
      <AppShell>
        <TaskBoard />
      </AppShell>
    );
  }

  return null;
}
