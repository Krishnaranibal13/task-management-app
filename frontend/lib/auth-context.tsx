"use client";

/**
 * Centralized auth/session state (Phase 5A).
 *
 * Security model:
 *  - Authentication = backend-issued HttpOnly session cookie only.
 *  - The raw CSRF token lives ONLY in a React ref (runtime memory).
 *    It is deliberately NOT in useState so it can never leak through
 *    devtools state dumps, and NEVER persisted anywhere.
 *  - On mount: GET /api/auth/me decides session existence; if
 *    authenticated, GET /api/auth/csrf rotates/refreshes the CSRF
 *    token into memory. 401 → clean login screen; 403 is NOT treated
 *    as logged-out.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { apiFetch, ApiError, type CurrentUser } from "./api";

type AuthStatus = "loading" | "unauthenticated" | "authenticated";

interface LoginResponse {
  csrf_token: string;
}

interface AuthContextValue {
  status: AuthStatus;
  user: CurrentUser | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<CurrentUser | null>(null);
  // Runtime-memory CSRF token. Never persisted; never rendered.
  const csrfRef = useRef<string | null>(null);

  const getCsrfToken = useCallback(() => csrfRef.current, []);

  const clearInMemoryState = useCallback(() => {
    setUser(null);
    csrfRef.current = null;
    setStatus("unauthenticated");
  }, []);

  /** Fetch current identity; returns null when unauthenticated (401). */
  const fetchMe = useCallback(async (): Promise<CurrentUser | null> => {
    try {
      return await apiFetch<CurrentUser>("/api/auth/me", {
        getCsrfToken,
        onUnauthorized: undefined, // bootstrap handles 401 itself
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return null;
      throw error;
    }
  }, [getCsrfToken]);

  /** Refresh the in-memory CSRF token for the EXISTING session. */
  const refreshCsrf = useCallback(async (): Promise<void> => {
    const data = await apiFetch<{ csrf_token: string }>("/api/auth/csrf", {
      getCsrfToken,
    });
    csrfRef.current = data.csrf_token;
  }, [getCsrfToken]);

  // Session bootstrap on mount / remount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await fetchMe();
        if (cancelled) return;
        if (me === null) {
          clearInMemoryState();
          return;
        }
        // Authenticated cookie survived: restore CSRF into memory.
        await refreshCsrf();
        if (cancelled) return;
        setUser(me);
        setStatus("authenticated");
      } catch {
        // Network/server trouble at startup → show login (no loop).
        if (!cancelled) clearInMemoryState();
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await apiFetch<LoginResponse>("/api/auth/login", {
        method: "POST",
        body: { email, password },
      });
      csrfRef.current = data.csrf_token;
      const me = await fetchMe();
      if (me === null) {
        // Should not happen right after a successful login.
        clearInMemoryState();
        throw new ApiError(401, "Invalid email or password.");
      }
      setUser(me);
      setStatus("authenticated");
      // Password is dropped immediately — never retained past login.
    },
    [fetchMe, clearInMemoryState],
  );

  const logout = useCallback(async (): Promise<void> => {
    // Server-side session revocation is AUTHORITATIVE. The frontend may
    // clear in-memory state ONLY when the backend confirms the session
    // is gone (or is provably already unusable). A network failure or a
    // server 5xx must NOT fake success — the user stays "logged in" and
    // can retry.
    //
    // Approved outcome matrix:
    //   success            → clear memory, show login UI
    //   401 (session gone) → session unusable; clearing is acceptable
    //   403 (stale CSRF)   → refresh CSRF once, retry ONCE (multi-tab fix)
    //   network error / 5xx / retry failure → keep state; sanitized UI error
    let lastError: unknown = null;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        await apiFetch<void>("/api/auth/logout", {
          method: "POST",
          getCsrfToken,
        });
        clearInMemoryState();
        return;
      } catch (error) {
        lastError = error;
        if (error instanceof ApiError && error.status === 401) {
          // Session already invalid/expired/revoked: nothing left to
          // revoke; clearing local state is honest here.
          clearInMemoryState();
          return;
        }
        if (
          error instanceof ApiError &&
          error.status === 403 &&
          attempt === 0
        ) {
          // Stale synchronizer token (e.g. another tab rotated it):
          // refresh ONCE and retry exactly once. No infinite loops.
          //
          // If the CSRF bootstrap itself fails with 401, the session is
          // provably already dead (expired/revoked/unknown): there is
          // nothing left to revoke, so clear local state and report
          // success instead of a bogus "Unable to log out". Any OTHER
          // refresh failure (network/5xx/etc.) keeps state and surfaces
          // the sanitized logout failure below.
          try {
            await refreshCsrf();
          } catch (refreshError) {
            if (
              refreshError instanceof ApiError &&
              refreshError.status === 401
            ) {
              clearInMemoryState();
              return;
            }
            break;
          }
          continue;
        }
        break; // network error / 5xx / second failure → do NOT fake success
      }
    }
    void lastError; // never logged: could contain request details
    throw new ApiError(0, "Unable to log out. Please try again.");
  }, [clearInMemoryState, getCsrfToken, refreshCsrf]);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, login, logout }),
    [status, user, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
