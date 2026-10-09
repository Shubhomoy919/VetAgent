import { expect, test, type APIRequestContext, type ConsoleMessage, type Page } from "@playwright/test";
import path from "node:path";

const SHOTS = path.resolve(import.meta.dirname, "../../docs/screenshots");
const REVIEWER = "e2e-reviewer";

test.describe.configure({ mode: "serial" });

function trackErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (m: ConsoleMessage) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(e.message));
  return errors;
}

async function cleanup(request: APIRequestContext) {
  const q = await (await request.get(`/api/review/queue?reviewer=${REVIEWER}`)).json();
  for (const item of q.items ?? []) {
    if (item.review) await request.delete(`/api/review?result_id=${item.result_id}&reviewer=${REVIEWER}`);
  }
  await request.delete("/api/settings");
  // Put back any local overrides (e.g. the chosen model) that existed before these tests.
  if (Object.keys(savedOverrides).length) await request.put("/api/settings", { data: savedOverrides });
}

let savedOverrides: Record<string, unknown> = {};

test.beforeAll(async ({ request }) => {
  const s = (await (await request.get("/api/settings")).json()) as { values: Record<string, unknown>; overridden: string[] };
  savedOverrides = Object.fromEntries(s.overridden.map((k) => [k, s.values[k]]));
});

test.afterAll(async ({ request }) => cleanup(request));

test("Runs: history and compare two runs", async ({ page, request }) => {
  const errors = trackErrors(page);
  const runs = (await (await request.get("/api/runs?limit=200")).json()) as { id: string; case_ids: string[]; interview: boolean; n_done: number }[];
  const full = runs.filter((r) => r.case_ids.length >= 25 && !r.interview && r.n_done > 0).slice(0, 2);
  expect(full.length).toBe(2);

  await page.goto("/");
  await page.getByRole("link", { name: "Runs" }).click();
  await expect(page.getByTestId("runs-table").locator("tbody tr")).toHaveCount(runs.length);
  for (const r of full) await page.locator(`[data-run-id="${r.id}"] input[type="checkbox"]`).check();
  const cmp = page.getByTestId("compare");
  await expect(cmp).toContainText("Changed verdicts");
  await expect(cmp.locator("tbody tr").first()).toBeVisible();
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(SHOTS, "m7-runs-1440.png") });
  await page.locator(".datapage").evaluate((el) => el.scrollTo(0, el.scrollHeight));
  await page.screenshot({ path: path.join(SHOTS, "m7-runs-compare-1440.png") });
  expect(errors).toEqual([]);
});

test("Review: rate with 1/2/N, agreement and kappa update", async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto("/review");
  await page.getByLabel("Reviewer").fill(REVIEWER);
  await expect(page.locator(".rv-progress")).toContainText(new RegExp(`0/\\d+ rated by ${REVIEWER}`));
  await expect(page.getByTestId("review-meta")).toHaveCount(0); // blind by default

  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("1");
  await expect(page.locator(".rv-progress")).toContainText("1/");
  await page.keyboard.press("2");
  await expect(page.locator(".rv-progress")).toContainText("2/");
  await page.keyboard.press("n");
  await expect(page.locator(".rv-progress")).toContainText("3/");
  await page.keyboard.press("1");
  await page.keyboard.press("1");
  await expect(page.locator(".rv-progress")).toContainText("5/");

  const stats = page.getByTestId("review-stats");
  await expect(stats).toContainText(REVIEWER);
  await expect(stats).toContainText("Cohen’s κ");
  await expect(stats).toContainText("1 unsure");

  await page.getByRole("button", { name: "Reveal condition & auto verdict" }).click();
  await expect(page.getByTestId("review-meta")).toBeVisible();
  await page.getByRole("button", { name: "Show gold" }).click();
  await expect(page.getByTestId("review-gold")).toBeVisible();
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(SHOTS, "m7-review-1440.png") });
  expect(errors).toEqual([]);
});

test("Study Design: ladder diagram, question types and metrics", async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto("/study");
  await expect(page.getByRole("img", { name: "Ablation ladder" })).toBeVisible();
  await expect(page.locator(".lf-track.on")).toHaveCount(10); // 0+1+2+3+4 components
  await expect(page.getByTestId("study-metrics").locator("tbody tr")).toHaveCount(10);
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SHOTS, "m7-study-1440.png") });
  expect(errors).toEqual([]);
});

test("Overview: status strip and latest results", async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto("/overview");
  await expect(page.locator(".ov-strip")).toContainText("29");
  await expect(page.getByTestId("chart-dangerous")).toBeVisible();
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SHOTS, "m7-overview-1440.png") });
  expect(errors).toEqual([]);
});

test("Settings: validation, save, reset, test connection, PDF status", async ({ page, request }) => {
  const errors = trackErrors(page);
  await page.goto("/settings");
  await expect(page.getByTestId("key-status")).toBeVisible();
  const body = await (await request.get("/api/settings")).text();
  expect(body).not.toMatch(/api_key/);

  // Server-side validation lands on the field.
  await page.getByLabel("Max tool steps (C2–C4)").fill("99");
  await page.getByTestId("save-settings").click();
  await expect(page.locator(".ff-error").first()).toContainText("less than or equal to 12");

  // Valid save, then reset back to .env.
  await page.getByLabel("Max tool steps (C2–C4)").fill("5");
  await page.getByTestId("save-settings").click();
  await expect(page.getByText("overridden in settings.json").first()).toBeVisible();
  expect((await (await request.get("/api/settings")).json()).values.max_steps).toBe(5);

  await page.getByTestId("test-connection").click();
  await expect(page.getByTestId("test-result")).toContainText("OK");
  await expect(page.getByTestId("usage")).toContainText("Total");
  await page.screenshot({ path: path.join(SHOTS, "m7-settings-1440.png") });

  page.once("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: "Reset to .env" }).click();
  await expect.poll(async () => (await (await request.get("/api/settings")).json()).overridden.length).toBe(0);

  // Reduced to what the study needs: no theme, density, palette, demo delay or price inputs.
  await expect(page.getByTestId("pdf-status")).toBeVisible();
  await expect(page.getByTestId("theme-swatches")).toHaveCount(0);
  await expect(page.getByTestId("palette")).toHaveCount(0);
  await expect(page.getByLabel("Demo delay (ms)")).toHaveCount(0);
  await expect(page.getByLabel("Input price")).toHaveCount(0);
  // The only console error allowed is the deliberate 422 from the invalid "99" save above.
  expect(errors.filter((e) => !e.includes("status of 422"))).toEqual([]);
});
