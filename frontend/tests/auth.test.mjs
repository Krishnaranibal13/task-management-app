/**
 * Frontend tests for the Phase 5A auth/session foundation.
 *
 * Runs with tsx (TypeScript execution without extra framework):
 *   npx tsx --test tests/auth.test.mjs
 *
 * Validates:
 *  - API client: credentials included, CSRF header only on mutations,
 *    sanitized errors, 401 handling
 *  - Security storage contract via AST analysis of PRODUCTION SOURCE:
 *    no executable references to localStorage/sessionStorage/indexedDB/
 *    document.cookie. Comments and documentation strings are ignored —
 *    only real executable code trips this test.
 *  - Auth form hygiene (no console logging, password cleared on failure)
 *  - LOGOUT SEMANTICS: authoritative server revocation; state is cleared
 *    ONLY on confirmed success or provably-dead session; network/5xx
 *    failures keep the user logged in; stale-CSRF retry happens at most
 *    once; failures surface a sanitized message.
 */

import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND = join(HERE, "..");

const PRODUCTION_SOURCES = [
  "lib/api.ts",
  "lib/auth-context.tsx",
  "app/page.tsx",
  "app/login-form.tsx",
  "app/app-shell.tsx",
  "app/layout.tsx",
];

/** Global object names that must never be referenced by production code. */
const BANNED_GLOBALS = new Set([
  "localStorage",
  "sessionStorage",
  "indexedDB",
]);

function collectViolations(source) {
  const sf = ts.createSourceFile(
    "module.tsx",
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX
  );
  const violations = [];

  function visit(node) {
    if (
      ts.isPropertyAccessExpression(node) &&
      ts.isIdentifier(node.expression) &&
      BANNED_GLOBALS.has(node.expression.text)
    ) {
      violations.push(`${node.expression.text}.${node.name.text}`);
    }
    if (
      ts.isPropertyAccessExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.expression.getText(sf) === "window" &&
      BANNED_GLOBALS.has(node.expression.name.text)
    ) {
      violations.push(`window.${node.expression.name.text}`);
    }
    if (
      ts.isPropertyAccessExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.expression.getText(sf) === "document" &&
      node.expression.name.text === "cookie"
    ) {
      violations.push("document.cookie");
    }
    if (ts.isIdentifier(node) && BANNED_GLOBALS.has(node.text)) {
      violations.push(`bare ${node.text}`);
    }
    node.forEachChild(visit);
  }

  sf.forEachChild(visit);
  return [...new Set(violations)];
}

for (const file of PRODUCTION_SOURCES) {
  test(`storage security (AST): ${file}`, () => {
    const source = readFileSync(join(FRONTEND, file), "utf8");
    assert.deepEqual(
      collectViolations(source),
      [],
      `${file} must not execute browser-storage APIs`
    );
  });
}

// ---------------------------------------------------------------------------
// API client behavior
// ---------------------------------------------------------------------------

test("CSRF header attached only to mutating requests", async () => {
  const { apiFetch } = await import("../lib/api.ts");
  let seen;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (_input, init) => {
    seen = init ?? {};
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  };

  try {
    await apiFetch("/api/auth/me", { getCsrfToken: () => "tok-123" });
    assert.ok(!seen.headers?.["X-CSRF-Token"], "GET must not send CSRF header");

    await apiFetch("/api/auth/logout", {
      method: "POST",
      getCsrfToken: () => "tok-123",
    });
    assert.equal(seen.headers["X-CSRF-Token"], "tok-123");
    assert.equal(seen.credentials, "include");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("401 surfaces sanitized error without echoing bodies", async () => {
  const { apiFetch } = await import("../lib/api.ts");
  const SECRET = "SUPER-SECRET-BODY";
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: SECRET }), { status: 401 });
  try {
    await assert.rejects(
      () => apiFetch("/api/auth/me", {}),
      (err) => err.status === 401 && !String(err).includes(SECRET)
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("password hygiene in login form source", () => {
  const form = readFileSync(join(FRONTEND, "app/login-form.tsx"), "utf8");
  assert.ok(form.includes('setPassword("")'), "password reset after failure");
  assert.ok(!/console\.(log|info|debug|error)/.test(form), "no console logging");
});

// ---------------------------------------------------------------------------
// LOGOUT SEMANTICS — exercised through the compiled AuthProvider module
// ---------------------------------------------------------------------------

/**
 * Harness: renders nothing but drives AuthProvider imperatively via the
 * context value, with a fully mocked fetch. Returns the live context so
 * tests can observe status/user transitions and drive login/logout.
 */
async function makeHarness() {
  const React = require("react");
  const { renderToStaticMarkup } = require("react-dom/server");
  void renderToStaticMarkup; // not needed for imperative driving

  // react-dom/client act() environment without a DOM: use a minimal stub.
  // AuthProvider only uses useState/useRef/useEffect/useMemo/useCallback —
  // all of which work in react-test-renderer-free mode via a fake host.
  let ctxValue = null;

  function Capture({ children }) {
    ctxValue = children;
    return null;
  }

  const { AuthProvider } = await import("../lib/auth-context.tsx");
  const element = React.createElement(
    AuthProvider,
    null,
    React.createElement(Capture, null)
  );

  // Minimal renderer: walk effects manually.
  require("react-dom"); // ensure scheduler side-effects are registered
  const { act } = require("react");
  // Without react-test-renderer, simulate mount by rendering to string and
  // flushing effects via the react-reconciler's synchronous pass is not
  // available — instead we call the provider body indirectly through
  // useSyncExternal-free logic: we simply invoke the exported provider in
  // test mode using ReactDOMServer to initialize hooks, then re-render on
  // state changes via repeated static renders driven by our fetch mocks.
  const { renderToString } = require("react-dom/server");

  let current = null;
  function rerender() {
    current = renderToString(
      React.createElement(AuthProvider, null, React.createElement(Capture))
    );
  }

  // Because reading context outside a renderer is awkward, expose the
  // captured context value from the last render instead.
  rerender();

  return {
    get value() {
      return ctxValue;
    },
    rerender,
  };
}

// Source-level logout contract (precise structural checks).
// NOTE: these deliberately assert on the compiled-from-source structure
// because AuthProvider's hook lifecycle cannot run under bare node:test;
// the BEHAVIORAL proof of the same contract lives in tests/browser-flows.mjs
// flows F/G (real Chromium + real backend).
test("logout clears state ONLY on confirmed success or dead session", () => {
  const src = readFileSync(join(FRONTEND, "lib/auth-context.tsx"), "utf8");
  const seg = src.split("const logout = useCallback")[1];

  // No unconditional finally-clear anymore.
  assert.ok(
    !/finally\s*\{[\s\S]*?clearInMemoryState\(\)[\s\S]*?\}/.test(seg),
    "logout must not clear state in an unconditional finally"
  );
  // Success path clears exactly once.
  assert.ok(
    /await apiFetch<void>\("\/api\/auth\/logout"[\s\S]{0,200}?clearInMemoryState\(\);\s*return;/.test(seg),
    "success path must clear state then return"
  );
  // 401 → acceptable clear (session already gone). The clear sits in the
  // catch block after the status check.
  assert.ok(
    /status === 401\)\s*\{[^}]*clearInMemoryState\(\);\s*return;/.test(seg),
    "401 during logout may honestly clear state"
  );
  // Stale-CSRF retry: refresh once, retry once (bounded loop).
  assert.match(seg, /attempt < 2/, "retry loop must be bounded");
  assert.match(seg, /refreshCsrf\(\)/, "stale-CSRF fix must refresh token");
  // Failure path throws sanitized error WITHOUT clearing.
  assert.match(seg, /Unable to log out\. Please try again\./);
  const failIdx = seg.indexOf("Unable to log out.");
  const clearAfterFail = seg.slice(failIdx).includes("clearInMemoryState()");
  assert.ok(!clearAfterFail, "failure path must NOT clear authenticated state");
});

test("CSRF-refresh 401 during logout = dead session: clears and succeeds", () => {
  const src = readFileSync(join(FRONTEND, "lib/auth-context.tsx"), "utf8");
  const seg = src.split("const logout = useCallback")[1];
  const refreshCatch = seg.split("await refreshCsrf();")[1] ?? "";
  // The refresh failure handler inspects the error status...
  assert.ok(
    /catch\s*\(refreshError\)[\s\S]*?status === 401/.test(refreshCatch),
    "refresh-failure branch must distinguish 401"
  );
  // ...and on 401 clears state AND returns success (no thrown error).
  const idx401 = refreshCatch.indexOf("status === 401");
  const after = refreshCatch.slice(idx401);
  const cleared = /clearInMemoryState\(\)/.test(after.slice(0, 300));
  assert.ok(cleared, "dead session via csrf-401 must clear local auth state");
  const returns = /return;/.test(after.slice(0, 400));
  assert.ok(returns, "logout resolves successfully (no bogus failure UI)");
});

test("CSRF-refresh non-401 failures keep authenticated state", () => {
  const src = readFileSync(join(FRONTEND, "lib/auth-context.tsx"), "utf8");
  const seg = src.split("const logout = useCallback")[1];
  const refreshCatch = seg.split("await refreshCsrf();")[1] ?? "";
  const idx401 = refreshCatch.indexOf("status === 401");
  const after401block = refreshCatch.slice(idx401);
  // After the 401 branch, any other error breaks out (no clear) and the
  // sanitized failure below runs.
  assert.match(after401block, /break;/, "non-401 refresh failure stops retrying");
  assert.ok(
    !/break;[\s\S]{0,80}clearInMemoryState\(\)/.test(after401block),
    "non-401 refresh failure must NOT clear state"
  );
});

test("AppShell surfaces sanitized logout failure, keeps button usable", () => {
  const shell = readFileSync(join(FRONTEND, "app/app-shell.tsx"), "utf8");
  assert.ok(shell.includes("Unable to log out. Please try again."));
  assert.match(shell, /role="alert"/);
  assert.ok(shell.includes("disabled={loggingOut}"), "button usable for retry");
  assert.ok(!/console\.(log|info|debug|error)/.test(shell), "no console logging");
});
