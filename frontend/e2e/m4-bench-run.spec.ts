import { expect, test, type ConsoleMessage } from "@playwright/test";
import path from "node:path";

const SHOTS = path.resolve(import.meta.dirname, "../../docs/screenshots");
const CONDS = ["C0", "C1", "C2", "C3", "C4"];

test.describe.configure({ mode: "serial" });

test("run BOV-WD-007 from the Bench: steps stream in, five cards finish with stamps", async ({ page }) => {
  test.setTimeout(120_000);
  const errors: string[] = [];
  page.on("console", (m: ConsoleMessage) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(e.message));

  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/?case=BOV-WD-007");
  await expect(page.getByTestId("case-species")).toHaveText("cattle");

  await page.locator("body").click({ position: { x: 5, y: 300 } });
  await page.keyboard.press("Shift+R"); // force re-run so nothing comes from cache

  // Streaming: run status changes and a card shows live steps before the run ends.
  await expect(page.getByTestId("run-status")).toContainText("Running", { timeout: 10_000 });
  const runningCard = page.locator('.ccard[data-status="running"]').first();
  await expect(runningCard).toBeVisible({ timeout: 10_000 });
  await expect(runningCard.locator(".log-step").first()).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: path.join(SHOTS, "m4-bench-running-1440-cyanotype.png") });

  await expect(page.getByTestId("run-status")).toHaveText("Done 5/5", { timeout: 90_000 });
  for (const c of CONDS) {
    const card = page.getByTestId(`card-${c}`);
    await expect(card).toHaveAttribute("data-status", "done");
    await expect(card.locator(".ccard-dx-value")).not.toBeEmpty();
  }
  await expect(page.locator(".stamp").first()).toBeVisible();
  await expect(page.locator('[data-case-id="BOV-WD-007"] .result-dot')).not.toHaveAttribute("data-state", "none");
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(SHOTS, "m4-bench-after-run-1440-cyanotype.png") });

  // Citation chip opens the SVTG passage drawer.
  await page.getByTestId("card-C2").locator(".cite-chip").first().click();
  const drawer = page.getByTestId("passage-drawer");
  await expect(drawer).toContainText("PDF page");
  await expect(drawer.locator(".drawer-chunk").first()).toBeVisible();
  await page.screenshot({ path: path.join(SHOTS, "m4-passage-drawer-1440-cyanotype.png") });
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);

  // C4 trace ends with the guardrail step.
  const c4 = page.getByTestId("card-C4");
  await c4.locator(".trace-toggle").click();
  await expect(c4.locator('.log-step[data-kind="rule"]')).toHaveCount(1);
  await expect(c4.locator('.log-step[data-kind="verify"]')).toHaveCount(1);

  expect(errors, errors.join("\n")).toEqual([]);
});

test("cards reload from storage after a page refresh", async ({ page }) => {
  await page.goto("/?case=BOV-WD-007");
  for (const c of CONDS) await expect(page.getByTestId(`card-${c}`)).toHaveAttribute("data-status", "done");
  await page.getByTestId("card-C2").locator(".trace-toggle").click();
  await expect(page.getByTestId("card-C2").locator(".log-step").first()).toBeVisible();
});

test("owner-interview mode runs only C0 and C3", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/?case=CAN-013");
  await page.getByLabel("Owner interview").check();
  await expect(page).toHaveURL(/mode=interview/);
  await expect(page.getByTestId("card-C1")).toContainText("Not part of owner-interview mode");
  await page.getByRole("button", { name: /Run case/ }).click();
  await expect(page.getByTestId("run-status")).toHaveText(/Done 2\/2/, { timeout: 60_000 });
  await expect(page.getByTestId("card-C3")).toContainText("Questions asked");
  await expect(page.getByTestId("card-C0")).toHaveAttribute("data-status", "done");
});

test("compare mode shows the chosen conditions side by side; Cyanotype screenshot", async ({ page }) => {
  await page.goto("/?case=BOV-WD-007");
  await page.getByRole("button", { name: "Compare" }).click();
  await expect(page.locator(".deck")).toHaveAttribute("data-mode", "compare");
  await expect(page.locator(".ccard")).toHaveCount(2); // default C0 vs C4
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(SHOTS, "m4-bench-compare-1440-cyanotype.png") });
});
