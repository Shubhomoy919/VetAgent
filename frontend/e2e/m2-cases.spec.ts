import { expect, test, type ConsoleMessage, type Page } from "@playwright/test";
import path from "node:path";

const SHOTS = path.resolve(import.meta.dirname, "../../docs/screenshots");
// Scope to the case listbox: the question-type <select> also has role="option" children.
const caseRows = (page: Page) => page.getByRole("listbox", { name: "Cases" }).getByRole("option");

test("case list shows ID, species, weight and type for every case", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("console", (m: ConsoleMessage) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(e.message));

  const cases = (await (await request.get("/api/cases")).json()) as {
    case_id: string;
    species: string;
    signalment: { weight_kg: number };
  }[];
  expect(cases.length).toBeGreaterThanOrEqual(25);

  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  const rows = caseRows(page);
  await expect(rows).toHaveCount(cases.length);

  for (const c of cases) {
    const row = page.locator(`[data-case-id="${c.case_id}"]`);
    await expect(row).toContainText(c.case_id);
    await expect(row.locator(".case-row-species")).toHaveText(c.species);
    await expect(row.locator(".case-row-weight")).toHaveText(`${c.signalment.weight_kg} kg`);
    await expect(row.locator(".type-pill")).toBeVisible();
    await expect(row.locator(".unverified-tag")).toBeVisible();
  }
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(SHOTS, "m2-case-list-1440-light.png") });
  expect(errors).toEqual([]);
});

test("BOV-WD-007 shows cattle with signalment and a gold answer behind Reveal", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/?case=BOV-WD-007");
  const detail = page.getByTestId("case-detail");
  await expect(detail).toContainText("BOV-WD-007");
  await expect(page.getByTestId("case-species")).toHaveText("cattle");
  await expect(detail).toContainText("410 kg");
  await expect(page.getByTestId("gold-answer")).toHaveCount(0);

  await page.getByTestId("reveal-gold").click();
  const gold = page.getByTestId("gold-answer");
  await expect(gold).toContainText("2 days");
  await expect(gold).toContainText("SVTG p.175");
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(SHOTS, "m2-case-detail-1440-light.png") });
});

test("filters and J/K navigation", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "FEL" }).click();
  await expect(caseRows(page)).toHaveCount(3);
  await page.getByRole("button", { name: "All", exact: true }).click();

  await page.getByLabel("Search cases").fill("anthrax");
  await expect(caseRows(page)).toHaveCount(1);
  await page.getByLabel("Search cases").fill("");

  await page.locator("body").click();
  await page.keyboard.press("j");
  const first = await caseRows(page).first().getAttribute("data-case-id");
  await expect(page).toHaveURL(new RegExp(`case=${first}`));
  await page.keyboard.press("j");
  const second = await caseRows(page).nth(1).getAttribute("data-case-id");
  await expect(page).toHaveURL(new RegExp(`case=${second}`));
  await page.keyboard.press("k");
  await expect(page).toHaveURL(new RegExp(`case=${first}`));
});

test("dark theme case detail screenshot", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/?case=FEL-SAFE-004");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByTestId("reveal-gold").click();
  await expect(page.getByTestId("gold-answer")).toContainText("contraindicated");
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(SHOTS, "m2-case-detail-1440-dark.png") });
});
