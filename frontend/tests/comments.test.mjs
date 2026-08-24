/**
 * Phase 5C tests: Comments API client + UI contracts.
 *
 * Same harness as tasks.test.mjs (node:test via tsx, mocked fetch for
 * behavioral API tests; precise source assertions for UI contracts).
 */

import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const FRONTEND = join(import.meta.dirname, "..");
const read = (p) => readFileSync(join(FRONTEND, p), "utf8");

// ---------------------------------------------------------------------------
// API client behavior (mocked fetch through the real module)
// ---------------------------------------------------------------------------

function withFetch(handler) {
  const original = globalThis.fetch;
  globalThis.fetch = handler;
  return () => {
    globalThis.fetch = original;
  };
}

test("listComments GETs /api/tasks/{id}/comments without CSRF header", async () => {
  const mod = await import("../lib/tasks-api.ts");
  let seen;
  const restore = withFetch(async (_url, init) => {
    seen = init ?? {};
    return new Response(JSON.stringify([]), { status: 200 });
  });
  try {
    const list = await mod.listComments(9, { getCsrfToken: () => "tok" });
    assert.deepEqual(list, []);
    assert.equal(seen.method ?? "GET", "GET");
    assert.equal(seen.headers["X-CSRF-Token"], undefined);
    assert.equal(seen.credentials, "include");
  } finally {
    restore();
  }
});

test("createComment POSTs to the task-scoped route", async () => {
  const mod = await import("../lib/tasks-api.ts");
  let seenUrl;
  let seenMethod;
  const restore = withFetch(async (url, init) => {
    seenUrl = String(url);
    seenMethod = init.method;
    return new Response(
      JSON.stringify({ id: 1, task_id: 9, user_id: 2, content: "x", created_at: "t" }),
      { status: 201 },
    );
  });
  try {
    await mod.createComment(9, { content: "hello" }, { getCsrfToken: () => "tok-1" });
    assert.ok(seenUrl.endsWith("/api/tasks/9/comments"));
    assert.equal(seenMethod, "POST");
  } finally {
    restore();
  }
});

test("createComment sends body EXACTLY {content}", async () => {
  const mod = await import("../lib/tasks-api.ts");
  let seenBody;
  const restore = withFetch(async (_url, init) => {
    seenBody = JSON.parse(init.body);
    return new Response(JSON.stringify({ id: 1 }), { status: 201 });
  });
  try {
    await mod.createComment(3, { content: "only content" }, { getCsrfToken: () => "t" });
    assert.deepEqual(seenBody, { content: "only content" });
    assert.deepEqual(Object.keys(seenBody), ["content"]);
    for (const banned of ["user_id", "task_id", "author", "created_at", "role"]) {
      assert.ok(!(banned in seenBody), `${banned} must never be sent`);
    }
  } finally {
    restore();
  }
});

test("createComment carries CSRF header through centralized apiFetch", async () => {
  const mod = await import("../lib/tasks-api.ts");
  let seenHeaders;
  const restore = withFetch(async (_url, init) => {
    seenHeaders = init.headers;
    return new Response(JSON.stringify({ id: 1 }), { status: 201 });
  });
  try {
    await mod.createComment(3, { content: "x" }, { getCsrfToken: () => "csrf-77" });
    assert.equal(seenHeaders["X-CSRF-Token"], "csrf-77");
  } finally {
    restore();
  }
});

test("403 on comment POST surfaces sanitized ApiError (no retry)", async () => {
  const mod = await import("../lib/tasks-api.ts");
  const { ApiError } = await import("../lib/api.ts");
  let calls = 0;
  const restore = withFetch(async () => {
    calls += 1;
    return new Response(JSON.stringify({ detail: "Forbidden" }), { status: 403 });
  });
  try {
    await assert.rejects(
      () => mod.createComment(3, { content: "x" }, { getCsrfToken: () => "t" }),
      (err) => err instanceof ApiError && err.status === 403,
    );
    assert.equal(calls, 1, "must not retry after 403");
  } finally {
    restore();
  }
});

// ---------------------------------------------------------------------------
// UI contracts (source assertions)
// ---------------------------------------------------------------------------

test("panel exposes loading, empty and error states", () => {
  const src = read("app/comments-panel.tsx");
  assert.match(src, /Loading comments…/);
  assert.match(src, /No comments yet\./);
  assert.match(src, /role="alert"/);
  assert.match(src, /Retry/);
});

test("author resolution uses directory email with neutral fallback", () => {
  const src = read("app/comments-panel.tsx");
  assert.match(src, /users\.find\(\(u\) => u\.id === userId\)\?\.email/);
  assert.match(src, /Unknown user/);
  // Never renders a raw user id as identity.
  assert.ok(!/{c\.user_id}/.test(src));
});

test("empty or whitespace-only submissions are prevented", () => {
  const src = read("app/comments-panel.tsx");
  assert.match(src, /content\.trim\(\)/);
  assert.match(src, /disabled=\{posting \|\| content\.trim\(\) === ""\}/);
});

test("no edit/delete/moderation controls exist anywhere in comments UI", () => {
  // Strip ALL block comments (they document prohibitions, not controls),
  // then scan the executable JSX/TS only.
  const src = read("app/comments-panel.tsx")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "")
    .toLowerCase();
  for (const banned of ["edit", ">delete<", "moderat", "mention", "attachment"]) {
    assert.ok(!src.includes(banned), `forbidden control/concept: ${banned}`);
  }
  // No interactive element may be labeled Edit/Delete/Moderate.
  assert.ok(!/>edit<|>delete<|>moderate</i.test(src));
});

test("dialog semantics + keyboard close present", () => {
  const src = read("app/comments-panel.tsx");
  assert.match(src, /role="dialog"/);
  assert.match(src, /aria-modal="true"/);
  assert.match(src, /aria-labelledby="comments-title"/);
  assert.match(src, /aria-label="Close comments"/);
  assert.match(src, /Escape/);
  assert.match(src, /Visible task context|Comments · \{task\.title\}/);
});

test("unknown role receives NO comment mutation control (fail-closed)", () => {
  const board = read("app/task-board.tsx");
  const panel = read("app/comments-panel.tsx");
  // Board computes the gate as an explicit approved-role whitelist.
  assert.match(
    board,
    /const canComment = role === "pm" \|\| role === "developer";/,
  );
  // The gate is passed into the panel (default false → fail-closed).
  assert.match(board, /canComment=\{canComment\}/);
  assert.match(panel, /canComment = false/);
  // Panel renders the POST form ONLY when canComment is true; otherwise
  // an explicit view-only notice replaces the entire mutation form.
  const gateIdx = panel.indexOf("{canComment ? (");
  const formIdx = panel.indexOf('className="comment-form"');
  const readOnlyIdx = panel.indexOf("Viewing comments is read-only.");
  assert.ok(gateIdx > -1 && readOnlyIdx > gateIdx);
  assert.ok(formIdx > gateIdx, "form must be inside the canComment branch");
});

test("board card has a Comments action for BOTH roles", () => {
  const board = read("app/task-board.tsx");
  assert.match(board, /aria-label=\{`Comments for \$\{task\.title\}`\}/);
  // The button sits OUTSIDE any role gate (rendered unconditionally per card).
  const idx = board.indexOf('setCommentsTask(task)}');
  const isPmIdx = board.lastIndexOf("{isPm && (", idx);
  const closeIdx = board.indexOf(")}", isPmIdx);
  assert.ok(idx > closeIdx, "comments button must be outside the PM-only block");
});

test("backend-confirmed append only — no fake comment fabrication", () => {
  const src = read("app/comments-panel.tsx");
  assert.match(src, /setComments\(\(prev\) => \[\.\.\.prev, created\]\)/);
  assert.ok(!/Date\.now\(\)|crypto\.randomUUID/.test(src));
});

test("no security-state persistence in comments code", () => {
  const src = read("app/comments-panel.tsx") + read("app/task-board.tsx");
  assert.ok(!/localStorage|sessionStorage|indexedDB|document\.cookie/.test(src));
});
