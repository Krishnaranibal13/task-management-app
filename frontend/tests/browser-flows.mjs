/**
 * Browser Automation flows for Phase 5A (real Chromium via playwright-core
 * driving the system-installed Edge; no extra framework).
 *
 * Flows validated (against the RUNNING stack):
 *   A. unauthenticated app  → login page visible
 *   B. valid PM login       → authenticated shell (role label)
 *   C. valid Developer login→ authenticated shell (role label)
 *   D. wrong password       → generic error, no existence leak
 *   E. refresh while authed → session survives, CSRF re-bootstrapped
 *   F. logout               → backend revoked + login page shown
 *   G. refresh after logout → still logged out
 *   H. direct load with valid cookie → bootstrap succeeds
 *
 * Security assertions inside the browser:
 *   - localStorage / sessionStorage hold NO auth material
 *   - NO application-created IndexedDB databases at all
 *   - session cookie not readable via document.cookie (HttpOnly)
 *   - CSRF token never rendered into DOM text or URLs
 */

import { chromium } from "playwright-core";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE = process.env.FRONTEND_URL ?? "http://localhost:3000";
const API = process.env.BACKEND_URL ?? "http://localhost:8000";

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

/**
 * REAL browser-side storage assertions.
 *  - localStorage/sessionStorage: enumerate keys+values, fail on ANY entry
 *    containing auth material (session tokens, csrf tokens, user JSON,
 *    passwords) — and for this MVP the app must create none at all.
 *  - IndexedDB: use indexedDB.databases() when available and assert the
 *    application created no databases; fall back to opening the well-known
 *    names it would have used if databases() is unsupported.
 *  - document.cookie: session cookie must NOT be readable (HttpOnly).
 */
async function storageAudit(page) {
  return page.evaluate(async () => {
    const AUTH_MARKERS = [
      "csrf",
      "session",
      "token",
      "user_id",
      "password",
      "auth",
    ];
    const containsAuthMaterial = (entries) =>
      entries.some(([k, v]) => {
        const hay = `${k}=${v}`.toLowerCase();
        return AUTH_MARKERS.some((m) => hay.includes(m));
      });

    const ls = Object.entries(localStorage);
    const ss = Object.entries(sessionStorage);

    let idbNames = null;
    try {
      if (typeof indexedDB.databases === "function") {
        const dbs = await indexedDB.databases();
        idbNames = (dbs ?? []).map((d) => d.name).filter(Boolean);
      } else {
        // Fallback: probe well-known candidate names via open() timeout.
        idbNames = [];
        const candidates = ["taskmgmt", "auth", "keyval"];
        await Promise.all(
          candidates.map(
            (name) =>
              new Promise((resolve) => {
                let settled = false;
                const done = (exists) => {
                  if (!settled) {
                    settled = true;
                    if (exists) idbNames.push(name);
                    resolve();
                  }
                };
                const req = indexedDB.open(name);
                req.onupgradeneeded = () => done(true);
                req.onsuccess = () => {
                  req.result.close();
                  done(true);
                };
                req.onerror = () => done(false);
                setTimeout(() => done(false), 500);
              })
          )
        );
      }
    } catch {
      idbNames = [];
    }

    return {
      lsEntries: ls.map(([k]) => k),
      ssEntries: ss.map(([k]) => k),
      lsHasAuth: containsAuthMaterial(ls),
      ssHasAuth: containsAuthMaterial(ss),
      idbNames,
      cookieReadableSession: document.cookie.includes("session"),
    };
  });
}

/**
 * Assert no opaque token appears in rendered text or current URL.
 * Precise approach:
 *  - word-bounded 43+ char runs on the ORIGINAL text (no whitespace
 *    stripping — stripping concatenates normal labels into fake matches)
 *  - if actual captured token values are provided, assert those EXACT
 *    strings never appear in the DOM or the page URL
 */
async function assertNoTokenExposure(page, label, knownTokens = []) {
  const bodyText = (await page.textContent("body")) ?? "";
  // Exclude Next.js internal asset names (e.g.
  // "node_modules_next_dist_client_components_builtin_global-error_…")
  // which are long but are build artifacts, not credentials. Real CSRF
  // tokens from our backend are exactly 43 chars of [A-Za-z0-9_-] and
  // never contain underscores adjacent to path-like segments such as
  // "_next_" or "node_modules".
  const cleaned = bodyText
    // Next.js internal asset/build identifiers (long but not credentials):
    .replace(/node_modules[\w-]*|_next_[\w-]*/g, "")
    // Next.js font module identifiers embedded in the RSC payload, e.g.
    // geist_mono_8d43a2aa-module__8Li5zG__variable — these are CSS class
    // hashes shipped in every Next.js app, never credentials.
    .replace(/geist_[\w-]*/g, "")
    .replace(/[\w-]*module__[\w-]*/g, "");
  const opaqueRun = /\b[A-Za-z0-9_-]{43,}\b/.test(cleaned);
  check(`${label}: no opaque token-like run in DOM`, !opaqueRun);
  for (const tok of knownTokens) {
    if (!tok) continue;
    check(`${label}: captured CSRF token absent from DOM`,
      !bodyText.includes(tok));
    check(`${label}: captured CSRF token absent from URL`,
      !page.url().includes(tok));
  }
}

async function login(page, email, password) {
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForSelector("#email", { timeout: 15000 });
  await page.fill("#email", email);
  await page.fill("#password", password);
  await page.click("button[type=submit]");
}

async function run() {
  const userDataDir = mkdtempSync(join(tmpdir(), "pw-profile-"));
  void userDataDir;
  const browser = await chromium.launch({
    channel: "msedge",
    headless: true,
    args: ["--no-sandbox"],
  });

  try {
    // ---------- Flow A: unauthenticated ----------
    const ctxA = await browser.newContext({
      viewport: { width: 1280, height: 900 },
    });
    const pageA = await ctxA.newPage();
    await pageA.goto(BASE, { waitUntil: "networkidle" });
    await pageA.waitForSelector("#email", { timeout: 15000 });
    check("A: unauthenticated shows login form",
      (await pageA.isVisible("#email")) && (await pageA.isVisible("#password")));

    const secA = await storageAudit(pageA);
    check("A: localStorage empty of auth material",
      !secA.lsHasAuth && secA.lsEntries.length === 0);
    check("A: sessionStorage empty of auth material",
      !secA.ssHasAuth && secA.ssEntries.length === 0);
    check("A: no application-created IndexedDB databases",
      Array.isArray(secA.idbNames) && secA.idbNames.length === 0);
    check("A: session cookie not JS-readable (HttpOnly)",
      !secA.cookieReadableSession);
    await ctxA.close();

    // ---------- Flow D: wrong password ----------
    const ctxD = await browser.newContext();
    const pageD = await ctxD.newPage();
    await pageD.goto(BASE, { waitUntil: "networkidle" });
    await pageD.waitForSelector("#email");
    await pageD.fill("#email", "pm-5a@example.com");
    await pageD.fill("#password", "definitely-wrong");
    await pageD.click("button[type=submit]");
    await pageD.waitForSelector("[role=alert]", { timeout: 10000 });
    // Wait until the request truly finished (button leaves loading state).
    await pageD.waitForFunction(
      () => {
        const btn = document.querySelector("button[type=submit]");
        return btn !== null && btn.disabled === false;
      },
      { timeout: 10000 }
    );
    const errText = (await pageD.textContent("[role=alert]")) ?? "";
    check("D: generic invalid-credentials error shown",
      /invalid email or password/i.test(errText));
    check("D: no account-existence disclosure",
      !/exist|unknown user|wrong password|not found/i.test(errText));
    check("D: password field cleared after failure",
      (await pageD.inputValue("#password")) === "");
    await ctxD.close();

    // ---------- Flow B: valid PM login ----------
    const ctxPm = await browser.newContext();
    const pm = await ctxPm.newPage();
    let pmLoginToken = null;
    let pmBootToken = null;
    pm.on("response", async (r) => {
      try {
        if (r.url().endsWith("/api/auth/login") && r.request().method() === "POST") {
          pmLoginToken = (await r.json())?.csrf_token ?? null;
        }
        if (r.url().endsWith("/api/auth/csrf")) {
          pmBootToken = (await r.json())?.csrf_token ?? null;
        }
      } catch { /* non-JSON or already-consumed body */ }
    });
    await login(pm, "pm-5a@example.com", "pm-pass-5a");
    await pm.waitForSelector("#shell-heading", { timeout: 15000 });
    check("B: PM sees authenticated shell", await pm.isVisible("#shell-heading"));
    check("B: PM role label shown",
      ((await pm.textContent(".whoami")) ?? "").includes("Project Manager"));

    const secB = await storageAudit(pm);
    check("B: web storage still clean after login",
      !secB.lsHasAuth && !secB.ssHasAuth && secB.idbNames.length === 0);
    check("B: session cookie still HttpOnly", !secB.cookieReadableSession);
    await assertNoTokenExposure(pm, "B", [pmLoginToken, pmBootToken]);

    // ---------- Flow E: refresh while authenticated ----------
    const csrfCalls = [];
    pm.on("response", (r) => {
      if (r.url().endsWith("/api/auth/csrf")) csrfCalls.push(r.status());
    });
    await pm.reload({ waitUntil: "networkidle" });
    await pm.waitForSelector("#shell-heading", { timeout: 15000 });
    check("E: session survives refresh (cookie bootstrap)",
      await pm.isVisible("#shell-heading"));
    check("E: GET /api/auth/csrf restored CSRF state (200)",
      csrfCalls.includes(200));

    // ---------- F: logout revokes server-side ----------
    const meBefore = await pm.evaluate(async (api) => {
      const r = await fetch(`${api}/api/auth/me`, { credentials: "include" });
      return r.status;
    }, API);
    check("F: pre-logout session active (me=200)", meBefore === 200);

    await pm.click("text=Log out");
    await pm.waitForSelector("#email", { timeout: 15000 });
    check("F: back at login after logout", await pm.isVisible("#email"));

    const meAfter = await pm.evaluate(async (api) => {
      const r = await fetch(`${api}/api/auth/me`, { credentials: "include" });
      return r.status;
    }, API);
    check("F: backend session revoked (me=401)", meAfter === 401);

    // ---------- G: refresh after logout ----------
    await pm.reload({ waitUntil: "networkidle" });
    await pm.waitForSelector("#email", { timeout: 15000 });
    check("G: refresh after logout stays logged out",
      await pm.isVisible("#email"));
    await ctxPm.close();

    // ---------- Flow C: valid Developer login ----------
    const ctxDev = await browser.newContext();
    const dev = await ctxDev.newPage();
    await login(dev, "dev-5a@example.com", "dev-pass-5a");
    await dev.waitForSelector("#shell-heading", { timeout: 15000 });
    check("C: Developer sees authenticated shell",
      await dev.isVisible("#shell-heading"));
    check("C: Developer role label shown",
      ((await dev.textContent(".whoami")) ?? "").includes("Developer"));
    const secC = await storageAudit(dev);
    check("C: developer context storage clean",
      !secC.lsHasAuth && !secC.ssHasAuth && secC.idbNames.length === 0);
    await ctxDev.close();

    // ---------- Flow H: direct load with valid cookie ----------
    const ctxH = await browser.newContext();
    const h = await ctxH.newPage();
    const apiLogin = await h.request.post(`${API}/api/auth/login`, {
      data: { email: "pm-5a@example.com", password: "pm-pass-5a" },
    });
    check("H: API login ok (plants HttpOnly cookie)", apiLogin.ok());
    const hCalls = [];
    h.on("response", (r) => {
      if (r.url().endsWith("/api/auth/me")) hCalls.push(["me", r.status()]);
      if (r.url().endsWith("/api/auth/csrf"))
        hCalls.push(["csrf", r.status()]);
    });
    await h.goto(BASE, { waitUntil: "networkidle" });
    await h.waitForSelector("#shell-heading", { timeout: 15000 });
    check("H: direct load bootstraps session", await h.isVisible("#shell-heading"));
    check("H: /me + /csrf both succeeded during bootstrap",
      hCalls.some(([p, s]) => p === "me" && s === 200) &&
      hCalls.some(([p, s]) => p === "csrf" && s === 200));
    const secH = await storageAudit(h);
    check("H: storage clean after direct-load bootstrap",
      !secH.lsHasAuth && !secH.ssHasAuth && secH.idbNames.length === 0);
    await ctxH.close();
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
