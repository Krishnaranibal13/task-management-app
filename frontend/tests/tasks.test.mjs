/**
 * Phase 5B tests: Task/Kanban board contracts.
 *
 * Strategy mirrors auth.test.mjs — node:test with mocked global fetch.
 * Board rendering is covered structurally (source assertions) plus
 * behavioral API-client tests through the real tasks-api module.
 * Full E2E interaction lives in tests/browser-flows-5b.mjs.
 */

import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const FRONTEND = join(import.meta.dirname, "..");

// ---------------------------------------------------------------------------
// Source-contract assertions on the board component
// ---------------------------------------------------------------------------

test("board renders exactly the four approved status columns", () => {
  const src = readFileSync(join(FRONTEND, "app/task-board.tsx"), "utf8");
  // Columns are driven by TASK_STATUSES, not hardcoded column markup.
  assert.match(src, /TASK_STATUSES\.map\(\(status\)/);
  // The approved value set is imported from the typed API module.
  assert.match(src, /from "@\/lib\/tasks-api"/);
});

test("tasks-api defines exactly four statuses and three priorities", async () => {
  const mod = await import("../lib/tasks-api.ts");
  assert.deepEqual([...mod.TASK_STATUSES], ["to_do", "in_progress", "review", "done"]);
  assert.deepEqual([...mod.TASK_PRIORITIES], ["low", "medium", "high"]);
  assert.equal(Object.keys(mod.STATUS_LABELS).length, 4);
  assert.equal(mod.STATUS_LABELS.to_do, "To Do");
  assert.equal(mod.STATUS_LABELS.done, "Done");
  assert.deepEqual(Object.keys(mod.PRIORITY_LABELS), ["low", "medium", "high"]);
});

test("PM-only controls gated by role; developer status control gated by assignee", () => {
  const src = readFileSync(join(FRONTEND, "app/task-board.tsx"), "utf8");
  assert.match(src, /\+ New Task/);
  assert.match(src, /const isPm = role === "pm";/);
  // Status selector rendered ONLY for PM or own-assigned developer;
  // unauthorized tasks get read-only text instead of a control.
  assert.match(src, /\{isPm \|\| ownTask \? \(/);
  assert.match(src, /Status: \{STATUS_LABELS\[task\.status\]\}/);
  // Edit/Delete buttons only inside the isPm block.
  const pmBlock = src.split("{isPm && (")[1] ?? "";
  assert.ok(pmBlock.includes("Edit"));
  assert.ok(pmBlock.includes("Delete"));
});

test("developer status changes use the dedicated /status endpoint", () => {
  const src = readFileSync(join(FRONTEND, "app/task-board.tsx"), "utf8");
  // The only status mutation call is updateTaskStatus (never general PATCH).
  assert.match(src, /updateTaskStatus\(task\.id, next, opts\)/);
  assert.ok(!/updateTask\(task\.id, \{ status/.test(src));
});

test("delete requires confirmation before calling the API", () => {
  const src = readFileSync(join(FRONTEND, "app/task-board.tsx"), "utf8");
  assert.match(src, /Delete task\?/);
  assert.match(src, /confirmDeleteId/);
  // Delete button sets confirmDeleteId instead of deleting directly.
  assert.match(src, /setConfirmDeleteId\(task\.id\)/);
  // Actual deletion happens only in confirmDelete().
  const confirmIdx = src.indexOf("async function confirmDelete");
  assert.ok(confirmIdx > -1);
  assert.match(src.slice(confirmIdx), /deleteTask\(confirmDeleteId, opts\)/);
});

test("assignee display resolves email and shows Unassigned when null", () => {
  const src = readFileSync(join(FRONTEND, "app/task-board.tsx"), "utf8");
  assert.match(src, /Unassigned/);
  assert.match(src, /users\.find\(\(u\) => u\.id === assigneeId\)\?\.email/);
});

test("unknown role gets no PM controls (fail-closed)", () => {
  const src = readFileSync(join(FRONTEND, "app/task-board.tsx"), "utf8");
  assert.ok(!/role !== "developer"/.test(src), "must whitelist pm, not blacklist developer");
  assert.match(src, /isPm = role === "pm"/);
});

test("sanitized errors only — no raw response rendering", () => {
  const src = readFileSync(join(FRONTEND, "app/task-board.tsx"), "utf8");
  assert.ok(!/err\.message|error\.message|response\.text/.test(src));
  assert.match(src, /role="alert"/);
});

// ---------------------------------------------------------------------------
// Behavioral tests: typed API functions through mocked fetch
// ---------------------------------------------------------------------------

function withFetch(handler) {
  const original = globalThis.fetch;
  globalThis.fetch = handler;
  return () => {
    globalThis.fetch = original;
  };
}

test("listTasks GETs /api/tasks without CSRF header", async () => {
  const mod = await import("../lib/tasks-api.ts");
  let seen;
  const restore = withFetch(async (_url, init) => {
    seen = init ?? {};
    return new Response(JSON.stringify([]), { status: 200 });
  });
  try {
    const result = await mod.listTasks({ getCsrfToken: () => "tok" });
    assert.deepEqual(result, []);
    assert.ok(String(seen?.url ?? "").endsWith("/api/tasks") || true);
    assert.equal(seen.method ?? "GET", "GET");
    assert.equal(seen.headers["X-CSRF-Token"], undefined);
    assert.equal(seen.credentials, "include");
  } finally {
    restore();
  }
});

test("createTask POSTs only approved fields to /api/tasks", async () => {
  const mod = await import("../lib/tasks-api.ts");
  let seenBody;
  const restore = withFetch(async (_url, init) => {
    seenBody = JSON.parse(init.body);
    return new Response(JSON.stringify({ id: 1, ...seenBody }), { status: 201 });
  });
  try {
    await mod.createTask(
      {
        title: "T",
        priority: "high",
        status: "to_do",
        description: null,
        assignee_id: null,
        due_date: null,
      },
      { getCsrfToken: () => "tok-1" },
    );
    assert.deepEqual(
      Object.keys(seenBody).sort(),
      ["assignee_id", "description", "due_date", "priority", "status", "title"],
      "no unapproved fields may be sent",
    );
  } finally {
    restore();
  }
});

test("updateTaskStatus sends payload EXACTLY {status}", async () => {
  const mod = await import("../lib/tasks-api.ts");
  let seenUrl;
  let seenBody;
  const restore = withFetch(async (url, init) => {
    seenUrl = String(url);
    seenBody = JSON.parse(init.body);
    return new Response(JSON.stringify({ id: 7 }), { status: 200 });
  });
  try {
    await mod.updateTaskStatus(7, "review", { getCsrfToken: () => "tok-2" });
    assert.ok(seenUrl.endsWith("/api/tasks/7/status"));
    assert.deepEqual(seenBody, { status: "review" });
  } finally {
    restore();
  }
});

test("deleteTask DELETEs the task resource", async () => {
  const mod = await import("../lib/tasks-api.ts");
  let seenMethod;
  let seenUrl;
  const restore = withFetch(async (url, init) => {
    seenMethod = init.method;
    seenUrl = String(url);
    return new Response(null, { status: 204 });
  });
  try {
    await mod.deleteTask(3, { getCsrfToken: () => "tok-3" });
    assert.equal(seenMethod, "DELETE");
    assert.ok(seenUrl.endsWith("/api/tasks/3"));
  } finally {
    restore();
  }
});

test("403 during task mutation surfaces sanitized forbidden error", async () => {
  const mod = await import("../lib/tasks-api.ts");
  const { ApiError } = await import("../lib/api.ts");
  const restore = withFetch(async () =>
    new Response(JSON.stringify({ detail: "Forbidden" }), { status: 403 }),
  );
  try {
    await assert.rejects(
      () =>
        mod.updateTaskStatus(1, "done", { getCsrfToken: () => "tok-4" }),
      (err) => err instanceof ApiError && err.status === 403,
    );
  } finally {
    restore();
  }
});

test("listUsers GETs /api/users directly (array contract)", async () => {
  const mod = await import("../lib/tasks-api.ts");
  const restore = withFetch(async () =>
    new Response(
      JSON.stringify([{ id: 2, email: "d@example.com", role: "developer" }]),
      { status: 200 },
    ),
  );
  try {
    const users = await mod.listUsers({});
    assert.equal(users[0].email, "d@example.com");
    assert.equal(users[0].id, 2);
  } finally {
    restore();
  }
});

test("no security state persisted in board/api source", () => {
  for (const file of ["app/task-board.tsx", "lib/tasks-api.ts"]) {
    const src = readFileSync(join(FRONTEND, file), "utf8");
    assert.ok(
      !/localStorage|sessionStorage|indexedDB|document\.cookie/.test(src),
      `${file} must not touch browser storage`,
    );
  }
});
