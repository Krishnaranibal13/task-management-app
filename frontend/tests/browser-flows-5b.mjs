/**
 * Browser Automation flows for Phase 5B (real Chromium via playwright-core
 * driving system Edge; same pattern as tests/browser-flows.mjs).
 *
 * Flows:
 *   A. PM login → Kanban visible, exactly four columns
 *   B. PM creates task (assignee from directory) → appears in chosen column
 *   C. PM edits title/priority/due date → UI reflects backend values
 *   D. PM reassigns → assignee display changes
 *   E. PM changes status → task moves column
 *   F. PM delete: confirmation shown, Cancel preserves, Delete removes
 *   G. Developer login → no + New Task, no edit/delete controls
 *   H. Developer sees all tasks with readable assignee emails
 *   I. Developer own assigned task → status control; dedicated /status
 *      request observed with payload exactly {status}
 *   J. Developer other/unassigned tasks → no status mutation control
 *   K. Refresh → backend state preserved
 *   L. storage-security audit green throughout
 *
 * Run:  node tests/browser-flows-5b.mjs
 */

import { chromium } from "playwright-core";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE = process.env.FRONTEND_URL ?? "http://localhost:3000";
const API = process.env.BACKEND_URL ?? "http://localhost:8000";

const PM = { email: "pm-5b@example.com", password: "pm-pass-5b" };
const DEV = { email: "dev-5b@example.com", password: "dev-pass-5b" };
const DEV2 = { email: "dev2-5b@example.com", password: "dev2-pass-5b" };

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

/** Real browser-side security audit (same as Phase 5A flows). */
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
      lsEntries: ls,
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
  // Wait past the loading skeleton AND past the empty-board state until
  // the real Kanban grid renders (or tasks exist).
  await page.waitForFunction(
    () =>
      document.querySelectorAll("div.column").length === 4 ||
      document.body.textContent.includes("No tasks yet"),
    { timeout: 15000 },
  );
}

function columnLocator(page, label) {
  return page.locator(`div.column[aria-label^="Column ${label}"]`);
}

async function openTaskForm(page) {
  await page.click("text=+ New Task");
  await page.waitForSelector("#t-title", { timeout: 5000 });
}

async function fillAndSubmit(page, fields) {
  if (fields.title !== undefined) {
    await page.fill("#t-title", fields.title);
  }
  if (fields.assigneeLabel) {
    await page.selectOption("#t-assignee", { label: fields.assigneeLabel });
  }
  if (fields.priority) {
    await page.selectOption("#t-priority", { label: fields.priority });
  }
  if (fields.status) {
    await page.selectOption("#t-status", { label: fields.status });
  }
  if (fields.due_date) {
    await page.fill("#t-due", fields.due_date);
  }
  await page.click('button[type="submit"]');
}

async function run() {
  const profile = mkdtempSync(join(tmpdir(), "pw5b-"));
  void profile;
  const browser = await chromium.launch({
    channel: "msedge",
    headless: true,
    args: ["--no-sandbox"],
  });

  try {
    // ---------- A: PM login → board with four columns ----------
    const ctxPm = await browser.newContext();
    const pm = await ctxPm.newPage();
    await login(pm, PM.email, PM.password);

    check("A: Kanban board heading visible",
      await pm.isVisible("#board-heading"));
    // The four-column grid ALWAYS renders (even with zero tasks).
    const columnsEmpty = await pm.locator("div.column").count();
    check(`A: exactly four columns visible on empty board (got ${columnsEmpty})`,
      columnsEmpty === 4);
    for (const label of ["To Do", "In Progress", "Review", "Done"]) {
      check(`A: column "${label}" present before any task`,
        (await columnLocator(pm, label).count()) === 1);
    }
    const emptyMsg = await pm.isVisible("text=No tasks yet");
    check("A: zero-task state handled cleanly (empty-state hint)", emptyMsg);

    // ---------- B: PM creates task with directory assignee ----------
    await openTaskForm(pm);
    await fillAndSubmit(pm, {
      title: "P5B Create Task",
      assigneeLabel: "dev-5b@example.com (developer)",
      priority: "High",
      status: "To Do",
      due_date: "2026-12-24",
    });
    const createdCard = columnLocator(pm, "To Do").locator("article", {
      hasText: "P5B Create Task",
    });
    await createdCard.waitFor({ timeout: 5000 });
    check("B: created task appears in To Do column", await createdCard.isVisible());
    check("B: card shows directory email for assignee",
      (await createdCard.textContent()).includes("dev-5b@example.com"));
    check("B: card shows priority text (not color-only)",
      (await createdCard.textContent()).includes("Priority: High"));
    check("B: card shows due date",
      (await createdCard.textContent()).includes("2026-12-24"));

    // ---------- C: PM edits title/priority/due date ----------
    await createdCard.locator("button", { hasText: "Edit" }).click();
    // Keep the task assigned to dev-5b (flow I needs it) while editing
    // title/priority/due date only.
    await page_fillEdit(pm, {
      title: "P5B Edited Task",
      priority: "Medium",
      due_date: "2026-12-31",
    });
    // Explicitly keep dev-5b as assignee (selectOption by exact label).
    await pm.selectOption("#t-assignee", {
      label: "dev-5b@example.com (developer)",
    });
    await pm.click('button[type="submit"]:has-text("Save Changes")');
    const editedCard = columnLocator(pm, "To Do")
      .locator("article", { hasText: "P5B Edited Task" })
      .first();
    await editedCard.waitFor({ timeout: 5000 });
    check("C: edited title reflected", await editedCard.isVisible());
    check("C: edited priority reflected",
      (await editedCard.textContent()).includes("Priority: Medium"));
    check("C: edited due date reflected",
      (await editedCard.textContent()).includes("2026-12-31"));

    // ---------- D: PM reassigns to a DIFFERENT user (real identity change) ----------
    // Task currently shows dev-5b (set in B/C). Reassign explicitly to
    // dev2-5b and assert the EXACT new email is displayed.
    await editedCard.locator("button", { hasText: "Edit" }).click();
    await pm.selectOption("#t-assignee", {
      label: "dev2-5b@example.com (developer)",
    });
    await pm.click('button[type="submit"]:has-text("Save Changes")');
    await pm.waitForTimeout(600);
    const reassignedText = await editedCard.textContent();
    check("D: reassignment displays the NEW assignee dev2-5b@example.com",
      reassignedText.includes("Assignee: dev2-5b@example.com"));
    check("D: previous assignee dev-5b no longer displayed on the card",
      !reassignedText.includes("dev-5b@example.com"));

    // ---------- D2: reassign BACK to dev-5b for flows G-J ----------
    await editedCard.locator("button", { hasText: "Edit" }).click();
    await pm.selectOption("#t-assignee", {
      label: "dev-5b@example.com (developer)",
    });
    await pm.click('button[type="submit"]:has-text("Save Changes")');
    await pm.waitForTimeout(600);
    const backText = await editedCard.textContent();
    check("D2: task reassigned back to dev-5b@example.com",
      backText.includes("Assignee: dev-5b@example.com"));

    // ---------- E: PM status change moves the card ----------
    await columnLocator(pm, "To Do")
      .locator("select[aria-label^='Change status of P5B Edited Task']")
      .selectOption({ label: "In Progress" });
    const movedCard = columnLocator(pm, "In Progress").locator("article", {
      hasText: "P5B Edited Task",
    });
    await movedCard.waitFor({ timeout: 5000 });
    check("E: task moved to In Progress after status change",
      await movedCard.isVisible());

    // ---------- F: delete confirmation + cancel + confirm ----------
    await movedCard.locator("button", { hasText: "Delete" }).click();
    const confirmBox = pm.locator(".confirm-box");
    check("F: confirmation dialog appears", await confirmBox.isVisible());
    check("F: confirmation asks 'Delete task?'",
      (await confirmBox.textContent()).includes("Delete task?"));
    await confirmBox.locator("button", { hasText: "Cancel" }).click();
    check("F: Cancel preserves the task", await movedCard.isVisible());

    // Second task for confirmed deletion.
    await openTaskForm(pm);
    await fillAndSubmit(pm, { title: "P5B Delete Me", priority: "Low", status: "Done" });
    const delCard = columnLocator(pm, "Done").locator("article", {
      hasText: "P5B Delete Me",
    });
    await delCard.waitFor({ timeout: 5000 });
    await delCard.locator("button", { hasText: "Delete" }).click();
    await confirmBox.locator("button", { hasText: "Delete" }).click();
    await pm.waitForTimeout(600);
    check("F: confirmed Delete removes the task",
      (await columnLocator(pm, "Done").locator("article").count()) === 0 ||
      !(await delCard.isVisible()));

    // ---------- F2: create an UNASSIGNED task for Developer flow J ----------
    await openTaskForm(pm);
    await fillAndSubmit(pm, {
      title: "P5B Other Task",
      priority: "Low",
      status: "To Do",
    });
    const otherCardPm = columnLocator(pm, "To Do").locator("article", {
      hasText: "P5B Other Task",
    });
    await otherCardPm.waitFor({ timeout: 5000 });
    check("F2: unassigned second task created for developer scoping",
      await otherCardPm.isVisible());

    // ---------- G/H/I/J: Developer flows ----------
    const ctxDev = await browser.newContext();
    const dev = await ctxDev.newPage();

    // Track /status requests + payload for flow I.
    const statusRequests = [];
    dev.on("request", (req) => {
      if (req.url().endsWith("/status")) {
        statusRequests.push(req.postData());
      }
    });

    await login(dev, DEV.email, DEV.password);

    check("G: developer has no + New Task control",
      (await pm.isVisible.bind(pm)) ? !(await dev.isVisible("text=+ New Task")) : true);
    check("G: developer sees no Edit buttons",
      (await dev.locator("button:has-text('Edit')").count()) === 0);
    check("G: developer sees no Delete buttons",
      (await dev.locator("button:has-text('Delete')").count()) === 0);

    // H: readable assignees on all tasks
    const anyCardWithAssignee = dev.locator("article", {
      hasText: "Assignee:",
    });
    check("H: tasks show readable assignee emails for developer",
      (await anyCardWithAssignee.count()) >= 1);

    // I: own assigned task exposes a working status selector
    const ownSelect = dev.locator(
      "select[aria-label='Change status of P5B Edited Task']",
    );
    check("I: status selector enabled on own assigned task",
      await ownSelect.isEnabled());
    await ownSelect.selectOption({ label: "Review" });
    const reviewCard = columnLocator(dev, "Review").locator("article", {
      hasText: "P5B Edited Task",
    });
    await reviewCard.waitFor({ timeout: 5000 });
    check("I: own task moved to Review", await reviewCard.isVisible());
    check("I: exactly one dedicated /status request observed",
      statusRequests.length === 1);
    check("I: /status payload is EXACTLY {status}",
      (() => {
        try {
          const keys = Object.keys(JSON.parse(statusRequests[0] ?? "{}"));
          return keys.length === 1 && keys[0] === "status";
        } catch {
          return false;
        }
      })());

    // J: unauthorized tasks (the unassigned "P5B Other Task") expose NO
    // mutation selector — read-only status text is rendered instead.
    const foreignSelect = dev.locator(
      "select[aria-label='Change status of P5B Other Task']",
    );
    check("J: no status selector rendered for the unassigned task",
      (await foreignSelect.count()) === 0);
    const otherCard = dev.locator("article", { hasText: "P5B Other Task" });
    check("J: unassigned task visible to developer",
      await otherCard.isVisible());
    check("J: unauthorized task shows read-only status text",
      (await otherCard.textContent()).includes("Status:"));

    // L: storage audit in developer context
    const secDev = await storageAudit(dev);
    check("L: developer storage clean (no auth material)",
      !secDev.lsHasAuth && !secDev.ssHasAuth && secDev.idbNames.length === 0);
    check("L: session cookie not JS-readable (HttpOnly)",
      !secDev.cookieReadableSession);

    // ---------- K: refresh preserves backend state ----------
    await dev.reload({ waitUntil: "networkidle" });
    await dev.waitForSelector("#board-heading", { timeout: 15000 });
    const persisted = columnLocator(dev, "Review").locator("article", {
      hasText: "P5B Edited Task",
    });
    check("K: refresh keeps backend task state",
      await persisted.isVisible());
    const secK = await storageAudit(dev);
    check("K/L: storage still clean after refresh",
      !secK.lsHasAuth && !secK.ssHasAuth);

    await ctxDev.close();
    await ctxPm.close();
  } finally {
    await browser.close();
  }

  console.log(`\nRESULT: ${passed} passed, ${failed} failed`);
  process.exit(failed === 0 ? 0 : 1);
}

/** Helper used by flow C (edit without touching unchanged fields). */
async function page_fillEdit(page, fields) {
  if (fields.title !== undefined) await page.fill("#t-title", fields.title);
  if (fields.priority) await page.selectOption("#t-priority", { label: fields.priority });
  if (fields.due_date) await page.fill("#t-due", fields.due_date);
}

run().catch((err) => {
  console.error("FATAL:", err?.message ?? err);
  process.exit(1);
});
