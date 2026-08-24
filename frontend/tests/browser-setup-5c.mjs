/**
 * Phase 5C browser flows — setup helper: creates the two tasks the
 * comment flows require (PM session, via the real UI).
 *
 * Run BEFORE browser-flows-5c.mjs when the board is empty:
 *   node tests/browser-setup-5c.mjs
 */

import { chromium } from "playwright-core";

const BASE = process.env.FRONTEND_URL ?? "http://localhost:3000";
const PM = { email: "pm-5b@example.com", password: "pm-pass-5b" };

async function login(page, email, password) {
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForSelector("#email", { timeout: 15000 });
  await page.fill("#email", email);
  await page.fill("#password", password);
  await page.click("button[type=submit]");
  await page.waitForSelector("#board-heading", { timeout: 15000 });
}

async function createTask(page, title) {
  await page.click('button:has-text("+ New Task")');
  await page.waitForSelector("#t-title");
  await page.fill("#t-title", title);
  await page.selectOption("#t-priority", { label: "High" });
  await page.selectOption("#t-status", { label: "To Do" });
  await page.click('button[type="submit"]:has-text("Create Task")');
  await page
    .locator("article", { hasText: title })
    .first()
    .waitFor({ timeout: 5000 });
}

const browser = await chromium.launch({
  channel: "msedge",
  headless: true,
  args: ["--no-sandbox"],
});
try {
  const page = await (await browser.newContext()).newPage();
  await login(page, PM.email, PM.password);

  // P5C Task is assigned to dev-5b so flow F tests own-task commenting.
  await createTask(page, "P5C Task");
  await page.locator("article", { hasText: "P5C Task" }).first()
    .locator("button", { hasText: "Edit" }).click();
  await page.selectOption("#t-assignee", {
    label: "dev-5b@example.com (developer)",
  });
  await page.click('button[type="submit"]:has-text("Save Changes")');
  await page.waitForTimeout(600);

  await createTask(page, "P5C Unassigned Task");
  console.log("setup complete: P5C Task (assigned dev-5b), P5C Unassigned Task");
} finally {
  await browser.close();
}
