import { expect, test, type ConsoleMessage } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const SHOTS = path.resolve(import.meta.dirname, "../../docs/screenshots");
const EXPORTS = path.resolve(import.meta.dirname, "../../data/exports");

test("Scorecard renders real numbers, charts, tables and exports CSV", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("console", (m: ConsoleMessage) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(e.message));

  const sc = await (await request.get("/api/scorecard")).json();
  expect(sc.n_cases).toBeGreaterThanOrEqual(25);

  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await page.getByRole("link", { name: "Scorecard" }).click();
  await expect(page).toHaveURL(/\/scorecard/);
  await expect(page.getByRole("heading", { level: 1, name: "Scorecard" }).first()).toBeVisible();

  // Tiles show the scored case count; charts exist for every metric.
  await expect(page.locator(".sc-tile").first()).toContainText(String(sc.n_cases));
  for (const m of sc.metrics) await expect(page.getByTestId(`chart-${m.key}`)).toBeVisible();

  // The metrics table matches the API: top-1 for the first condition.
  const top1 = sc.metrics.find((m: { key: string }) => m.key === "dx_top1").by_condition[sc.conditions[0]];
  const rowText = await page.getByTestId("metrics-table").locator("tbody tr").first().innerText();
  expect(rowText).toContain(`${top1.k}/${top1.n}`);
  await expect(page.getByTestId("mcnemar-table")).toBeVisible();

  if (sc.run.provider === "demo") await expect(page.locator(".sc-warnings")).toContainText("Demo provider");

  // Hovering a dot shows its tooltip with the CI.
  await page.getByTestId("chart-dangerous").locator(".dw-row").first().hover();
  await expect(page.getByTestId("chart-dangerous").locator(".dw-tip")).toContainText("CI");

  await page.mouse.move(0, 0);
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SHOTS, "m5-scorecard-1440-light.png"), fullPage: false });
  await page.locator(".scorecard").evaluate((el) => el.scrollTo(0, el.scrollHeight));
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(SHOTS, "m5-scorecard-tables-1440-light.png") });

  // CSV export through the UI.
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export-csv").click()]);
  expect(download.suggestedFilename()).toMatch(/^scorecard-.*\.csv$/);
  fs.mkdirSync(EXPORTS, { recursive: true });
  const target = path.join(EXPORTS, download.suggestedFilename().replace(".csv", "-ui.csv"));
  await download.saveAs(target);
  const csv = fs.readFileSync(target, "utf-8");
  expect(csv.split("\n")[0]).toContain("metric,label,better,condition,k,n,rate,ci_low,ci_high");
  expect(csv).toContain("dx_top1");
  console.log(`CSV saved: ${target}`);

  expect(errors, errors.join("\n")).toEqual([]);
});

test("Scorecard dark theme", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/scorecard");
  await expect(page.getByTestId("chart-dx_top1")).toBeVisible();
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SHOTS, "m5-scorecard-1440-dark.png") });
});
