import { expect, test, type ConsoleMessage } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const SHOTS = path.resolve(import.meta.dirname, "../../docs/screenshots");
const DATA = path.resolve(import.meta.dirname, "../../data");
const FILES = ["cases.json", "drug_table.csv"];
const backups: Record<string, Buffer> = {};

test.describe.configure({ mode: "serial" });

// Edits go through the real API into data/; restore the committed files afterwards.
test.beforeAll(() => {
  for (const f of FILES) backups[f] = fs.readFileSync(path.join(DATA, f));
});
test.afterAll(() => {
  for (const f of FILES) fs.writeFileSync(path.join(DATA, f), backups[f] as Buffer);
});

test("Cases table: rows, unverified tags, sort and filter", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m: ConsoleMessage) => m.type() === "error" && errors.push(m.text()));
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await page.getByRole("link", { name: "Cases" }).click();
  const rows = page.getByTestId("cases-table").locator("tbody tr");
  await expect(rows).toHaveCount(29);
  await expect(rows.locator(".unverified-tag")).toHaveCount(29);

  await page.getByRole("button", { name: /^Weight/ }).click();
  await expect(rows.first()).toHaveAttribute("data-case-id", "AVI-004"); // 1.1 kg, lightest
  await page.getByRole("button", { name: /^Weight/ }).click();
  await expect(page.getByRole("columnheader", { name: /Weight/ })).toHaveAttribute("aria-sort", "descending");

  await page.getByRole("button", { name: "FEL", exact: true }).click();
  await expect(rows).toHaveCount(3);
  await page.getByRole("button", { name: "All", exact: true }).click();
  await page.getByRole("button", { name: /^Case/ }).click();
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(SHOTS, "m6-cases-1440-cyanotype.png") });
  expect(errors).toEqual([]);
});

test("Case editor: client and server validation, then a valid save", async ({ page, request }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/cases");
  await page.locator('[data-case-id="BOV-WD-007"]').click();
  const editor = page.getByTestId("case-editor");
  await expect(editor).toBeVisible();

  // 1. Client-side rule: cattle weight 250–600 kg.
  const weight = editor.getByLabel("Weight (kg)");
  await weight.fill("90");
  await editor.getByTestId("save-case").click();
  await expect(editor.getByText("Outside the cattle range (250–600 kg)").first()).toBeVisible();
  await expect(editor.getByTestId("error-summary")).toBeVisible();
  await expect(weight).toHaveAttribute("aria-invalid", "true");
  await page.screenshot({ path: path.join(SHOTS, "m6-case-editor-validation-1440-cyanotype.png") });
  const unchanged = await (await request.get("/api/cases/BOV-WD-007")).json();
  expect(unchanged.signalment.weight_kg).toBe(410);

  // 2. Server-side rule: renaming to an existing ID is rejected and shown on the field.
  await weight.fill("410");
  const id = editor.getByLabel("Case ID");
  await id.fill("BOV-002");
  await editor.getByTestId("save-case").click();
  await expect(editor.getByText("case_id BOV-002 already exists")).toBeVisible();

  // 3. Valid edit saves and persists.
  await id.fill("BOV-WD-007");
  const history = editor.getByLabel("History");
  await history.fill(`${unchanged.history} (edited in e2e)`);
  await editor.getByTestId("save-case").click();
  await expect(editor).toHaveCount(0);
  const saved = await (await request.get("/api/cases/BOV-WD-007")).json();
  expect(saved.history).toContain("(edited in e2e)");
});

test("Drug table: banned-drug rule blocks a dose; filter by status", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/drugs");
  const rows = page.getByTestId("drugs-table").locator("tbody tr");
  await expect(rows).toHaveCount(31);
  await expect(rows.locator(".unverified-tag")).toHaveCount(31);
  await page.screenshot({ path: path.join(SHOTS, "m6-drugs-1440-cyanotype.png") });

  await page.locator('[data-drug-key="cattle|diclofenac"]').click();
  const editor = page.getByTestId("drug-editor");
  await editor.getByLabel("Dose min (mg/kg)").fill("1");
  await editor.getByLabel("Dose max (mg/kg)").fill("2");
  await editor.getByTestId("save-drug").click();
  await expect(editor.getByText("Banned drugs must not carry a dose").first()).toBeVisible();
  await page.screenshot({ path: path.join(SHOTS, "m6-drug-editor-validation-1440-cyanotype.png") });
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "banned in india" }).click();
  await expect(rows).toHaveCount(8);
});

test("Data pages in Kalamkari", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("vab.theme", "kalamkari"));
  await page.goto("/cases");
  await expect(page.getByTestId("cases-table")).toBeVisible();
  await page.screenshot({ path: path.join(SHOTS, "m6-cases-1440-kalamkari.png") });
  await page.goto("/drugs");
  await expect(page.getByTestId("drugs-table")).toBeVisible();
  await page.screenshot({ path: path.join(SHOTS, "m6-drugs-1440-kalamkari.png") });
});
