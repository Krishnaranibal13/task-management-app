/**
 * Centralized API client for the Task Management MVP frontend.
 *
 * Security properties (Phase 5A):
 *  - The ONLY credential is the backend-issued HttpOnly session cookie;
 *    every request uses `credentials: "include"` so the browser attaches
 *    it automatically. This module never reads, writes, or stores cookies.
 *  - The raw CSRF token lives ONLY in runtime memory inside AuthProvider.
 *    It is NEVER written to localStorage / sessionStorage / IndexedDB /
 *    document.cookie and never appears in URLs or logs.
 *  - Mutating requests attach `X-CSRF-Token`; ordinary GETs do not.
 *  - Errors are sanitized: response bodies are parsed only to decide a
 *    generic message; passwords/tokens/cookies are never logged.
 */

/** Backend base URL (compose injects NEXT_PUBLIC_API_BASE_URL). */
export const API_BASE: string =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/** Product-useful identity fields for the authenticated UI. */
export interface CurrentUser {
  user_id: number;
  email: string;
  role: "pm" | "developer";
}

/** Sanitized application error — safe to surface in the UI. */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

/** Generic, non-revealing messages mapped from HTTP statuses. */
const GENERIC_MESSAGES: Record<number, string> = {
  400: "Invalid request.",
  401: "Invalid email or password.",
  403: "You are not allowed to perform that action.",
  404: "Not found.",
  422: "Invalid input.",
  429: "Too many attempts. Please wait and try again.",
};

function genericFor(status: number): string {
  return GENERIC_MESSAGES[status] ?? "Something went wrong. Please try again.";
}

export interface ApiClientOptions {
  /** In-memory CSRF token provider (set once the user is authenticated). */
  getCsrfToken?: () => string | null | undefined;
  /** Called when any request reports an expired/unknown session (401). */
  onUnauthorized?: () => void;
}

/**
 * Core request helper. Never throws raw network/parse details at callers:
 * everything surfaces as {@link ApiError} with a sanitized message.
 */
export async function apiFetch<T>(
  path: string,
  options: ApiClientOptions & {
    method?: string;
    body?: unknown;
  } = {},
): Promise<T> {
  const { getCsrfToken, onUnauthorized, method = "GET", body } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  // CSRF header ONLY on state-changing requests, never on plain GETs.
  if (method !== "GET" && method !== "HEAD") {
    const token = getCsrfToken?.();
    if (token) headers["X-CSRF-Token"] = token;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      credentials: "include", // HttpOnly session cookie travels automatically
      cache: "no-store",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Please try again.");
  }

  if (response.status === 401) {
    // Session missing/expired/revoked → caller resets in-memory state.
    onUnauthorized?.();
    throw new ApiError(401, genericFor(401));
  }

  if (!response.ok) {
    throw new ApiError(response.status, genericFor(response.status));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
