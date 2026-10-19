/* Acceptance checks for milestone M8, plus shortcuts and responsive layouts. */
import { expect, test, type ConsoleMessage, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const EXPORTS = path.resolve(import.meta.dirname, "../../data/exports");
const CONDS = ["C0", "C1", "C2", "C3", "C4"];

function trackErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (m: ConsoleMessage) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(e.message));
  return errors;
}

test.describe.configure({ mode: "serial" });

test('"/" opens the Bench', async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto("/");
  await expect(page.getByTestId("bench")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: "Bench" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("BOV-WD-007 shows cattle, and C0–C4 fill after a run", async ({ page }) => {
  test.setTimeout(120_000);
  const errors = trackErrors(page);
  await page.goto("/?case=BOV-WD-007");
  await expect(page.getByTestId("case-species")).toHaveText("cattle");
  await page.locator("body").click({ position: { x: 5, y: 400 } });
  await page.keyboard.press("Shift+R");
  await expect(page.getByTestId("run-status")).toHaveText("Done 5/5", { timeout: 90_000 });
  for (const c of CONDS) {
    await expect(page.getByTestId(`card-${c}`)).toHaveAttribute("data-status", "done");
    await expect(page.getByTestId(`card-${c}`).locator(".ccard-dx-value")).not.toBeEmpty();
  }
  expect(errors).toEqual([]);
});

test("Scorecard renders and exports CSV", async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto("/scorecard");
  await expect(page.getByTestId("chart-dx_top1")).toBeVisible();
  await expect(page.getByTestId("metrics-table").locator("tbody tr").first()).toBeVisible();
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export-csv").click()]);
  fs.mkdirSync(EXPORTS, { recursive: true });
  const target = path.join(EXPORTS, `m8-${download.suggestedFilename()}`);
  await download.saveAs(target);
  expect(fs.readFileSync(target, "utf-8").split("\n").find((l) => !l.startsWith("#"))).toContain("metric,label,better,condition,k,n,rate,ci_low,ci_high");
  expect(errors).toEqual([]);
});

test("Shortcuts: G reveals gold, J/K move, 1–5 jump, ? opens the shortcut sheet", async ({ page }) => {
  await page.goto("/?case=BOV-001");
  await page.locator("body").click({ position: { x: 5, y: 400 } });
  await page.keyboard.press("g");
  await expect(page.getByTestId("gold-answer")).toBeVisible();
  await page.keyboard.press("g");
  await expect(page.getByTestId("gold-answer")).toHaveCount(0);
  await page.keyboard.press("j");
  await expect(page).toHaveURL(/case=BOV-002/);
  await page.keyboard.press("k");
  await expect(page).toHaveURL(/case=BOV-001/);
  await page.keyboard.press("?");
  await expect(page.getByTestId("shortcuts-help")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("shortcuts-help")).toHaveCount(0);
});


test("1024–1439px: case list becomes a drawer", async ({ page }) => {
  await page.setViewportSize({ width: 1200, height: 800 });
  await page.goto("/?case=BOV-001");
  const drawer = page.getByTestId("cases-drawer");
  await expect(drawer).toHaveAttribute("data-open", "false");
  await page.getByTestId("open-cases").click();
  await expect(drawer).toHaveAttribute("data-open", "true");
  await drawer.locator('[data-case-id="CAP-001"]').click();
  await expect(drawer).toHaveAttribute("data-open", "false");
  await expect(page).toHaveURL(/case=CAP-001/);
  // J/K still work with the drawer closed.
  await page.locator("body").click({ position: { x: 600, y: 790 } });
  await page.keyboard.press("j");
  await expect(page).toHaveURL(/case=CAP-002/);
});

test("< 1024px: conditions show one at a time as tabs", async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 900 });
  await page.goto("/?case=BOV-WD-007");
  await expect(page.locator(".deck")).toHaveAttribute("data-mode", "tabs");
  await expect(page.locator(".ccard")).toHaveCount(1);
  await expect(page.getByTestId("card-C0")).toBeVisible();
  await page.locator("body").click({ position: { x: 5, y: 890 } });
  await page.keyboard.press("3");
  await expect(page.getByTestId("card-C2")).toBeVisible();
  await expect(page.locator(".ccard")).toHaveCount(1);
  await page.locator('.deck-tab[data-cond="C4"]').click();
  await expect(page.getByTestId("card-C4")).toBeVisible();
});

test("Reduced motion: page still renders and the scan line is static", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/scorecard");
  await expect(page.getByTestId("chart-dangerous")).toBeVisible();
  const dur = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--dur").trim());
  expect(dur).toBe("0ms");
});
