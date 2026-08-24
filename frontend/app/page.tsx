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
          <section className="card" aria-live="polite" aria-busy="true">
            <h1>Task Management MVP</h1>
            <p className="subtitle">Checking your session…</p>
          </section>
        )}

        {status === "unauthenticated" && <LoginForm />}

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
