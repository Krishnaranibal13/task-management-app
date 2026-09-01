"use client";

/**
 * Login form (Phase 5A).
 *
 * - Generic error text only: never reveals whether the email exists
 *   or the password was wrong (mirrors backend semantics).
 * - Accessible: labeled inputs, semantic form/button, visible focus,
 *   error announced via role="alert".
 */

import { FormEvent, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const GENERIC_LOGIN_ERROR = "Invalid email or password.";

export default function LoginForm() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      // Password is dropped with the component state on navigation;
      // nothing is stored or logged.
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError("Too many attempts. Please wait and try again.");
      } else {
        setError(GENERIC_LOGIN_ERROR);
      }
      setPassword("");
      // Focus password field after credential failure
      passwordRef.current?.focus();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="login-card" aria-labelledby="login-heading" style={{ margin: "auto", marginTop: "calc(50vh - 200px)" }}>
      <div className="appbar-logo" style={{ justifyContent: "center", marginBottom: "var(--space-4)" }} aria-hidden="true">
        <div className="appbar-logo-mark">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M9 11l3 3L22 4" />
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
          </svg>
        </div>
        <h1 id="login-heading" className="login-title">Task Management MVP</h1>
      </div>
      <p className="login-subtitle">Sign in to continue</p>

      <form onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="email" className="field-label">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={submitting}
            autoFocus
            className="field-input"
          />
        </div>

        <div className="field">
          <label htmlFor="password" className="field-label">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
            ref={passwordRef}
            className="field-input"
          />
        </div>

        {error !== null && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}

        <div className="form-actions" style={{ width: "100%" }}>
          <button type="submit" className="btn btn-primary" disabled={submitting} style={{ width: "100%" }}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </div>
      </form>
    </section>
  );
}