/* v1.0.0 release checks on the production build (see playwright.release.config.ts). */
import { expect, request, test, type ConsoleMessage, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const CODE = process.env.E2E_ACCESS_CODE ?? "";
const BUDGET_URL = process.env.E2E_BUDGET_URL ?? "";
const CONDS = ["C0", "C1", "C2", "C3", "C4"];
const OUT = path.resolve(import.meta.dirname, "../../data/exports");
const DISCLAIMER = "Research prototype, not for clinical use. Consult a registered veterinarian.";

function trackErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (m: ConsoleMessage) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(e.message));
  return errors;
}

test.describe.configure({ mode: "serial" });

test("health reports a production build with the frozen benchmark", async ({ request }) => {
  const h = await (await request.get("/api/health")).json();
  expect(h.environment).toBe("production");
  expect(h.version).toBe("1.0.0");
  expect(h.mode).toBe("public");
  expect(h.database.ok).toBe(true);
  expect(h.benchmark.version).toBe("1.0.0");
  expect(h.benchmark.frozen).toBe(true);
  expect(h.counts.runs).toBeGreaterThan(0);
  expect(JSON.stringify(h)).not.toMatch(/AIza|GEMINI_API_KEY|sk-/);
});

test.describe("public, read-only", () => {
  const pages: [string, string][] = [
    ["/overview", "overview-page"],
    ["/scorecard", "scorecard"],
    ["/cases", "cases-page"],
    ["/drugs", "drugs-page"],
    ["/runs", "runs-page"],
    ["/study", "study-page"],
    ["/", "bench"],
  ];

  for (const [url, testId] of pages) {
    test(`browse ${url} with no console errors`, async ({ page }) => {
      const errors = trackErrors(page);
      await page.goto(url);
      await expect(page.getByTestId(testId)).toBeVisible();
      await expect(page.locator(".footer")).toHaveText(DISCLAIMER);
      await expect(page.getByTestId("unlock")).toBeVisible();
      await expect(page.getByTestId("demo-banner")).toHaveCount(0);
      expect(errors).toEqual([]);
    });
  }

  test("Overview shows the benchmark version and hash", async ({ page }) => {
    await page.goto("/overview");
    await expect(page.getByTestId("benchmark-version")).toContainText(/Benchmark v1\.0\.0 content hash [0-9a-f]{12}, frozen/);
  });

  test("Bench shows a completed run and no run controls", async ({ page }) => {
    await page.goto("/?case=BOV-WD-007");
    await expect(page.getByTestId("case-species")).toHaveText("cattle");
    for (const c of CONDS) await expect(page.getByTestId(`card-${c}`)).toHaveAttribute("data-status", "done");
    await expect(page.getByRole("button", { name: /^Run case/ })).toHaveCount(0);
    await expect(page.getByTestId("readonly-note")).toBeVisible();
  });

  test("UNVERIFIED tags stay visible on cases and drug rows", async ({ page }) => {
    await page.goto("/cases");
    await expect(page.locator(".unverified-tag").first()).toBeVisible();
    await page.goto("/drugs");
    await expect(page.locator(".unverified-tag").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "New row" })).toHaveCount(0);
  });

  test("Review and Settings ask for the access code", async ({ page }) => {
    for (const url of ["/review", "/settings"]) {
      await page.goto(url);
      await expect(page.getByTestId("access-gate")).toBeVisible();
      await expect(page.getByLabel("Access code", { exact: true })).toBeVisible();
    }
  });

  test("an uncited SVTG page and the PDF itself are not served", async ({ request }) => {
    expect((await request.get("/api/svtg/pages/250")).status()).toBe(404);
    for (const u of ["/StandardVeterinaryTreatment.pdf", "/data/StandardVeterinaryTreatment.pdf"]) {
      const r = await request.get(u);
      expect(r.headers()["content-type"]).not.toContain("pdf");
    }
  });
});

test("a run is blocked without the access code", async ({ page, request }) => {
  const r = await request.post("/api/runs", { data: { case_ids: ["BOV-WD-007"] } });
  expect(r.status()).toBe(401);
  expect((await r.json()).detail).toContain("access code");
  await page.goto("/?case=BOV-WD-007");
  await page.locator("body").click({ position: { x: 5, y: 400 } });
  await page.keyboard.press("r");
  await expect(page.getByRole("dialog", { name: "Unlock runs and editing" })).toBeVisible();
  await expect(page.getByTestId("run-status")).toHaveText("Idle");
});

test("a wrong code is refused with attempts left", async ({ page }) => {
  await page.goto("/settings");
  await page.getByLabel("Access code", { exact: true }).fill("definitely-wrong");
  await page.getByRole("button", { name: "Unlock", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(/Wrong access code\. \d attempts? left\./);
});

test("with the access code: run BOV-WD-007 through C0–C4", async ({ page }) => {
  test.skip(!CODE, "E2E_ACCESS_CODE not set");
  test.setTimeout(240_000);
  const errors = trackErrors(page);
  await page.goto("/?case=BOV-WD-007");
  await page.getByTestId("unlock").click();
  await page.getByLabel("Access code", { exact: true }).fill(CODE);
  await page.getByRole("button", { name: "Unlock", exact: true }).click();
  await expect(page.getByTestId("lock")).toBeVisible();
  await page.getByRole("button", { name: /^Run case/ }).click();
  await expect(page.getByTestId("run-status")).toHaveText(/^Done(?: with errors)? 5\/5$/, { timeout: 200_000 });
  // A provider failure must show its real error on the card; report it rather than time out.
  const failed = page.locator("[data-testid^='card-'][data-status='error']");
  if ((await failed.count()) > 0) {
    throw new Error(`Live provider error on ${await failed.first().getAttribute("data-testid")}: ${(await failed.first().innerText()).slice(0, 300)}`);
  }
  for (const c of CONDS) {
    await expect(page.getByTestId(`card-${c}`)).toHaveAttribute("data-status", "done");
    await expect(page.getByTestId(`card-${c}`).locator(".ccard-dx-value")).not.toBeEmpty();
  }
  // Settings opens once unlocked; locking returns to read-only.
  await page.goto("/settings");
  await expect(page.getByTestId("settings-page")).toBeVisible();
  await page.getByTestId("lock").click();
  await expect(page.getByTestId("access-gate")).toBeVisible();
  expect(errors).toEqual([]);
});

test("Scorecard renders with provenance, and the CSV export carries it", async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto("/scorecard");
  await expect(page.getByTestId("chart-dx_top1")).toBeVisible();
  await expect(page.getByTestId("metrics-table").locator("tbody tr").first()).toBeVisible();
  await expect(page.getByTestId("provenance")).toContainText("Temperature");
  await expect(page.getByTestId("provenance")).toContainText("v1.0.0");
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export-csv").click()]);
  fs.mkdirSync(OUT, { recursive: true });
  const target = path.join(OUT, `release-${download.suggestedFilename()}`);
  await download.saveAs(target);
  const lines = fs.readFileSync(target, "utf-8").split(/\r?\n/);
  expect(lines[0]).toBe(`# disclaimer: ${DISCLAIMER}`);
  expect(lines.some((l) => /^# benchmark_hash: [0-9a-f]{64}$/.test(l))).toBe(true);
  expect(lines.some((l) => l.startsWith("# model: "))).toBe(true);
  expect(lines.find((l) => !l.startsWith("#"))).toContain("metric,label,better,condition,k,n,rate,ci_low,ci_high");
  expect(errors).toEqual([]);
});

test("the daily budget cap refuses new runs with a clear message", async () => {
  test.skip(!BUDGET_URL || !CODE, "E2E_BUDGET_URL / E2E_ACCESS_CODE not set");
  const ctx = await request.newContext({ baseURL: BUDGET_URL });
  const unlock = await ctx.post("/api/auth/unlock", { data: { code: CODE } });
  expect(unlock.status()).toBe(200);
  const cookie = (unlock.headers()["set-cookie"] ?? "").split(";")[0];
  const b = await (await ctx.get("/api/budget")).json();
  expect(b.exhausted).toBe(true);
  const r = await ctx.post("/api/runs", { data: { case_ids: ["BOV-WD-007"] }, headers: { Cookie: cookie } });
  expect(r.status()).toBe(429);
  expect((await r.json()).detail).toMatch(/^Daily token budget reached \([\d,]+ of [\d,]+ tokens used today\)/);
  await ctx.dispose();
});

test("keyboard only: skip link, navigation, access dialog, visible pink focus ring", async ({ page }) => {
  await page.goto("/overview");
  await expect(page.getByTestId("overview-page")).toBeVisible();
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#content")).toBeFocused();
  // The focus ring is the pink accent, at least 2px.
  await page.goto("/overview");
  await expect(page.getByTestId("overview-page")).toBeVisible();
  for (let i = 0; i < 3; i++) await page.keyboard.press("Tab");
  const ring = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement;
    const cs = getComputedStyle(el);
    return { tag: el.tagName, width: parseFloat(cs.outlineWidth), color: cs.outlineColor, style: cs.outlineStyle };
  });
  expect(ring.style).not.toBe("none");
  expect(ring.width).toBeGreaterThanOrEqual(2);
  // #FF4F9A, reported as rgb() or, when mixed through color-mix(), as its oklch equivalent.
  expect(ring.color).toMatch(/^(rgb\(255, 79, 154\)|oklch\(0\.69\d* 0\.2[12]\d* 35[89](\.\d+)?\))$/);
  // Reach the Unlock button by keyboard, open the dialog, close with Escape; focus returns.
  const unlock = page.getByTestId("unlock");
  await unlock.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Unlock runs and editing" });
  await expect(dialog).toBeVisible();
  await expect(page.getByLabel("Access code", { exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(unlock).toBeFocused();
  // Sidebar links are reachable and announce the current page.
  const nav = page.getByRole("complementary", { name: "Primary" });
  await nav.getByRole("link", { name: "Scorecard" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/scorecard$/);
  await expect(nav.getByRole("link", { name: "Scorecard" })).toHaveAttribute("aria-current", "page");
  await expect(page).toHaveTitle("Scorecard · VetAgentBench-IN");
});

test("screen-reader labels on dials, strips, stamps, traces and charts", async ({ page }) => {
  await page.goto("/?case=BOV-WD-007");
  await expect(page.getByTestId("dose-dial").first()).toHaveAttribute("aria-label", /Dose dial for /);
  await expect(page.getByTestId("triage-strip").first()).toHaveAttribute("aria-label", /^Triage: /);
  await expect(page.locator(".stamp .visually-hidden").first()).toHaveText(/^Verdict: /);
  await expect(page.locator(".vt-svg").first()).toHaveAttribute("aria-label", /Vital signs: /);
  await page.goto("/scorecard");
  await expect(page.locator("[data-testid^='chart-'] [aria-label]").first()).toHaveAttribute("aria-label", /.+/);
});
