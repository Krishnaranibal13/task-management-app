"use client";

/**
 * Login form (Phase 5A).
 *
 * - Generic error text only: never reveals whether the email exists
 *   or the password was wrong (mirrors backend semantics).
 * - Accessible: labeled inputs, semantic form/button, visible focus,
 *   error announced via role="alert".
 */

import { FormEvent, useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const GENERIC_LOGIN_ERROR = "Invalid email or password.";

export default function LoginForm() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="card" aria-labelledby="login-heading">
      <h1 id="login-heading">Task Management MVP</h1>
      <p className="subtitle">Sign in to continue</p>

      <form onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="email">Email</label>
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
          />
        </div>

        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
          />
        </div>

        {error !== null && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="primary" disabled={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </section>
  );
}
