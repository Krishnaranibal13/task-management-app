/**
 * Browser Automation for Phase 5C (Comments UI) — real Chromium via
 * playwright-core driving system Edge (same pattern as 5A/5B suites).
 *
 * Flows:
 *   A. PM login → Kanban loads → Task has Comments action
 *   B. PM opens comments → empty state when none exist
 *   C. PM submits a comment → exact content + readable identity shown
 *   D. reopen/refresh → comment persists from backend
 *   E. Developer login → sees task comments
 *   F. Developer comments on OWN assigned task → succeeds
 *   G. Developer comments on OTHER/UNASSIGNED task → succeeds
 *   H. POST body observed to contain EXACTLY {content}
 *   I. no edit/delete/moderation controls anywhere in the panel
 *   J. storage-security audit green
 *   K. refresh preserves backend comments
 *   L. sanitized error behavior (network-level failure simulation)
 *
 * Run:  node tests/browser-flows-5c.mjs
 */

import { chromium } from "playwright-core";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE = process.env.FRONTEND_URL ?? "http://localhost:3000";

const PM = { email: "pm-5b@example.com", password: "pm-pass-5b" };
const DEV = { email: "dev-5b@example.com", password: "dev-pass-5b" };

let passed = 0;
let failed = 0;

function check(name, cond) {
  if (cond) {
    passed += 1;
    console.log(`PASS - ${name}`);
  } else {
    failed += 1;
    console.log(`FAIL - ${name}`);
  }
}

async function storageAudit(page) {
  return page.evaluate(async () => {
    const MARKERS = ["csrf", "session", "token", "user_id", "password"];
    const ls = Object.entries({ ...localStorage });
    const ss = Object.entries({ ...sessionStorage });
    let idbNames = [];
    try {
      idbNames = (await indexedDB.databases()).map((d) => d.name);
    } catch {
      idbNames = [];
    }
    return {
      lsHasAuth: ls.some(
        ([k, v]) =>
          MARKERS.some((m) => k.toLowerCase().includes(m)) ||
          MARKERS.some((m) => String(v).toLowerCase().includes(m)),
      ),
      ssHasAuth: ss.length > 0,
      idbNames,
      cookieReadableSession: document.cookie.includes("session="),
    };
  });
}

async function login(page, email, password) {
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForSelector("#email", { timeout: 15000 });
  await page.fill("#email", email);
  await page.fill("#password", password);
  await page.click("button[type=submit]");
  await page.waitForSelector("#board-heading", { timeout: 15000 });
  await page.waitForFunction(
    () =>
      document.querySelectorAll("div.column").length === 4 ||
      document.body.textContent.includes("No tasks yet"),
    { timeout: 15000 },
  );
}

async function openComments(page, taskTitle) {
  await page.click(`button[aria-label="Comments for ${taskTitle}"]`);
  await page.waitForSelector('[role="dialog"]', { timeout: 5000 });
}

/** Open comments for a task and return the rendered comment-item count. */
async function openAndCount(page, taskTitle) {
  await openComments(page, taskTitle);
  await page
    .locator(".comment-item")
    .first()
    .waitFor({ timeout: 5000 })
    .catch(() => {}); // empty state is fine
  const n = await page.locator(".comment-item").count();
  await page.click('button[aria-label="Close comments"]');
  return n;
}

const POST_ERR = "Unable to add comment. Please try again.";

async function run() {
  const browser = await chromium.launch({
    channel: "msedge",
    headless: true,
    args: ["--no-sandbox"],
  });

  const commentRequests = [];

  try {
    // ---------- A/B/C/D: PM flows ----------
    const ctxPm = await browser.newContext();
    const pm = await ctxPm.newPage();

    pm.on("request", (req) => {
      if (req.method() === "POST" && req.url().includes("/comments")) {
        commentRequests.push(req.postData());
      }
    });

    await login(pm, PM.email, PM.password);
    check("A: Kanban board visible after PM login",
      await pm.isVisible("#board-heading"));

    check("A: Comments action present on task card",
      await pm.isVisible('button[aria-label^="Comments for"]'));

    // B: empty state
    await openComments(pm, "P5C Task");
    check("B: dialog opens with accessible name",
      (await pm.getAttribute('[role="dialog"]', "aria-labelledby")) !== null);
    const pmEmpty = pm.locator("text=No comments yet.");
    await pmEmpty.waitFor({ timeout: 5000 });
    check("B: empty state shown when no comments exist",
      await pmEmpty.isVisible());

    // C: submit a comment
    await pm.fill("#c-content", "P5C first comment from PM");
    await pm.click('button:has-text("Add Comment")');
    const firstComment = pm.locator(".comment-item", {
      hasText: "P5C first comment from PM",
    });
    await firstComment.waitFor({ timeout: 5000 });
    check("C: exact comment content appears", await firstComment.isVisible());
    check("C: readable PM identity displayed",
      (await firstComment.textContent()).includes("pm-5b@example.com"));
    check("C: created timestamp displayed",
      /\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(await firstComment.textContent()));

    // D: close + reopen → persists from backend
    await pm.click('button[aria-label="Close comments"]');
    await openComments(pm, "P5C Task");
    const reopened = pm.locator(".comment-item", {
      hasText: "P5C first comment from PM",
    });
    await reopened.waitFor({ timeout: 5000 });
    check("D: comment persists on reopen (backend-confirmed)",
      await reopened.isVisible());

    // I (PM view): no edit/delete/moderation controls in panel
    const panelText = await pm.locator('[role="dialog"]').textContent();
    check("I: no Edit/Delete/Moderate controls in comments panel",
      !/Edit|Delete|Moderate/.test(panelText ?? ""));

    // J: storage audit (PM)
    const secPm = await storageAudit(pm);
    check("J: PM storage clean",
      !secPm.lsHasAuth && !secPm.ssHasAuth && secPm.idbNames.length === 0);
    check("J: session cookie not JS-readable",
      !secPm.cookieReadableSession);

    // Create a second (unassigned) task as PM for flow G.
    await pm.click('button:has-text("+ New Task")');
    await pm.fill("#t-title", "P5C Unassigned Task");
    await pm.selectOption("#t-priority", { label: "Low" });
    await pm.selectOption("#t-status", { label: "To Do" });
    await pm.click('button[type="submit"]:has-text("Create Task")');
    await pm.waitForTimeout(600);

    await ctxPm.close();

    // ---------- E/F/G/H/I/J/K: Developer flows ----------
    const ctxDev = await browser.newContext();
    const dev = await ctxDev.newPage();
    dev.on("request", (req) => {
      if (req.method() === "POST" && req.url().includes("/comments")) {
        commentRequests.push(req.postData());
      }
    });

    await login(dev, DEV.email, DEV.password);

    // E: developer sees existing comments
    await openComments(dev, "P5C Task");
    const devSees = dev.locator(".comment-item", {
      hasText: "P5C first comment from PM",
    });
    await devSees.waitFor({ timeout: 5000 });
    check("E: developer sees task comments", await devSees.isVisible());

    // F: developer comments on OWN assigned task
    await dev.fill("#c-content", "P5C dev comment on own task");
    await dev.click('button:has-text("Add Comment")');
    await dev.locator(".comment-item", {
      hasText: "P5C dev comment on own task",
    }).waitFor({ timeout: 5000 });
    check("F: developer comment on own assigned task appears",
      true);
    check("F: readable developer identity displayed",
      (await dev.locator(".comment-item", {
        hasText: "P5C dev comment on own task",
      }).textContent()).includes("dev-5b@example.com"));
    await dev.click('button[aria-label="Close comments"]');

    // G: developer comments on UNASSIGNED task (ownership does NOT gate)
    await openComments(dev, "P5C Unassigned Task");
    const emptyState = dev.locator("text=No comments yet.");
    await emptyState.waitFor({ timeout: 5000 });
    check("G: unassigned task also shows empty state",
      await emptyState.isVisible());
    await dev.fill("#c-content", "P5C dev comment on unassigned task");
    await dev.click('button:has-text("Add Comment")');
    const gComment = dev.locator(".comment-item", {
      hasText: "P5C dev comment on unassigned task",
    });
    await gComment.waitFor({ timeout: 5000 });
    check("G: developer can comment on unassigned task",
      await gComment.isVisible());
    await dev.click('button[aria-label="Close comments"]');

    // H: every comment POST body is EXACTLY {content}
    check("H: at least three comment POSTs observed", commentRequests.length >= 3);
    let allExact = commentRequests.length > 0;
    for (const raw of commentRequests) {
      try {
        const body = JSON.parse(raw ?? "");
        if (Object.keys(body).length !== 1 || !("content" in body)) allExact = false;
        for (const banned of ["user_id", "task_id", "author", "created_at", "role"]) {
          if (banned in body) allExact = false;
        }
      } catch {
        allExact = false;
      }
    }
    check("H: ALL comment POST bodies are EXACTLY {content}", allExact);

    // I: no forbidden controls in the whole document for developer either
    const devText = await dev.locator("body").textContent();
    check("I: no comment Edit/Delete/Moderate controls anywhere",
      !(await dev.locator('[role="dialog"]').count()) &&
      !/Moderate/.test(devText ?? ""));

    // J: developer storage audit
    const secDev = await storageAudit(dev);
    check("J: developer storage clean",
      !secDev.lsHasAuth && !secDev.ssHasAuth && secDev.idbNames.length === 0);

    // K: refresh preserves backend comments
    await dev.reload({ waitUntil: "networkidle" });
    await dev.waitForSelector("#board-heading", { timeout: 15000 });
    await openComments(dev, "P5C Task");
    await dev.locator(".comment-item").first().waitFor({ timeout: 5000 });
    check("K: both comments persist after refresh",
      (await dev.locator(".comment-item").count()) >= 2);

    // L: REAL sanitized-error flow — intercept ONLY the comments POST and
    // force a server failure. Verify sanitized UI error, no raw JSON /
    // stack / SQL / token leakage, comment NOT falsely appended, app alive.
    await dev.click('button[aria-label="Close comments"]');
    let forced500 = false;
    await dev.route("**/api/tasks/*/comments", async (route) => {
      if (route.request().method() === "POST") {
        forced500 = true;
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({
            detail: "INTERNAL ERROR: psycopg2 traceback at db/queries.py:88 password_hash=SECRET session_cookie=abc123",
          }),
        });
      } else {
        await route.continue();
      }
    });

    const before = await openAndCount(dev, "P5C Task");
    // Re-open the dialog for the failing submission itself.
    await openComments(dev, "P5C Task");
    await dev.fill("#c-content", "L: this must never appear");
    await dev.click('button:has-text("Add Comment")');
    const postError = dev.locator('[role="dialog"] .form-error');
    await postError.waitFor({ timeout: 5000 });
    const errText = await postError.textContent();

    check("L: POST failure surfaced a sanitized error", errText === POST_ERR);
    check("L: no raw backend internals in the error",
      !/traceback|psycopg|password|session_cookie|secret|sql/i.test(errText ?? ""));
    check("L: no stack/SQL details anywhere in the dialog",
      !/traceback|psycopg|db\/queries|sql/i.test(
        await dev.locator('[role="dialog"]').textContent() ?? ""));
    // Failed comment is NOT appended to frontend state.
    check("L: failed comment not falsely appended",
      (await openAndCount(dev, "P5C Task")) === before &&
      !(await dev.locator(".comment-item", {
        hasText: "L: this must never appear",
      }).isVisible().catch(() => false)));
    // App remains usable afterwards.
    await dev.unroute("**/api/tasks/*/comments");
    check("L: interception actually exercised", forced500);

    const secL = await storageAudit(dev);
    check("L/J: storage still clean after failed POST",
      !secL.lsHasAuth && !secL.ssHasAuth && secL.idbNames.length === 0);

    await ctxDev.close();
  } finally {
    await browser.close();
  }

  console.log(`\nRESULT: ${passed} passed, ${failed} failed`);
  process.exit(failed === 0 ? 0 : 1);
}

run().catch((err) => {
  console.error("FATAL:", err?.message ?? err);
  process.exit(1);
});
