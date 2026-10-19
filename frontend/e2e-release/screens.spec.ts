/* Every page and state at 1440, 1024 and 768 px on the production build, with zero console errors.
 * Screenshots go to docs/screenshots/release/. States: public (read-only), unlocked, access prompt,
 * loading, empty, error/offline, 404. */
import { expect, test, type ConsoleMessage, type Page } from "@playwright/test";
import path from "node:path";

const OUT = path.resolve(import.meta.dirname, "../../docs/screenshots/release");
const CODE = process.env.E2E_ACCESS_CODE ?? "";
const WIDTHS = [1440, 1024, 768] as const;
const PAGES: [string, string, string][] = [
  ["bench", "/?case=BOV-WD-007", "bench"],
  ["overview", "/overview", "overview-page"],
  ["scorecard", "/scorecard", "scorecard"],
  ["cases", "/cases", "cases-page"],
  ["drugs", "/drugs", "drugs-page"],
  ["runs", "/runs", "runs-page"],
  ["study", "/study", "study-page"],
];

function trackErrors(page: Page, allow: RegExp[] = []): string[] {
  const errors: string[] = [];
  page.on("console", (m: ConsoleMessage) => {
    if (m.type() === "error" && !allow.some((a) => a.test(m.text()))) errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(e.message));
  return errors;
}

async function noHorizontalScroll(page: Page) {
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(over, "page scrolls sideways").toBeLessThanOrEqual(1);
}

async function shot(page: Page, name: string) {
  await page.waitForTimeout(450); // let 80–320 ms entrances settle
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: false });
}

test.describe.configure({ mode: "serial" });

for (const w of WIDTHS) {
  test.describe(`${w}px`, () => {
    test.use({ viewport: { width: w, height: w === 768 ? 1024 : 900 } });

    for (const [name, url, testId] of PAGES) {
      test(`public ${name}`, async ({ page }) => {
        const errors = trackErrors(page);
        await page.goto(url);
        await expect(page.getByTestId(testId)).toBeVisible();
        await noHorizontalScroll(page);
        await shot(page, `${name}-public-${w}`);
        expect(errors).toEqual([]);
      });
    }

    test("access prompt (Review, Settings) and dialog", async ({ page }) => {
      const errors = trackErrors(page);
      await page.goto("/review");
      await expect(page.getByTestId("access-gate")).toBeVisible();
      await noHorizontalScroll(page);
      await shot(page, `review-access-prompt-${w}`);
      await page.goto("/settings");
      await expect(page.getByTestId("access-gate")).toBeVisible();
      await shot(page, `settings-access-prompt-${w}`);
      await page.goto("/");
      await page.getByTestId("unlock").click();
      await expect(page.getByRole("dialog", { name: "Unlock runs and editing" })).toBeVisible();
      await shot(page, `access-dialog-${w}`);
      expect(errors).toEqual([]);
    });

    test("404", async ({ page }) => {
      const errors = trackErrors(page);
      await page.goto("/no-such-page");
      await expect(page.getByRole("heading", { level: 1 })).toContainText(/not found/i);
      await noHorizontalScroll(page);
      await shot(page, `404-${w}`);
      expect(errors).toEqual([]);
    });

    test("loading state", async ({ page }) => {
      await page.route("**/api/scorecard**", async (route) => {
        await new Promise((r) => setTimeout(r, 2500));
        await route.continue();
      });
      await page.goto("/scorecard");
      await expect(page.getByText("Scoring…")).toBeVisible();
      await shot(page, `scorecard-loading-${w}`);
    });

    test("empty state", async ({ page }) => {
      await page.route("**/api/scorecard**", (route) =>
        route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "No runs with results yet. Run cases from the Bench first." }) }),
      );
      await page.route("**/api/runs?**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
      const errors = trackErrors(page, [/404/]);
      await page.goto("/scorecard");
      await expect(page.getByText("No scorecard yet")).toBeVisible();
      await shot(page, `scorecard-empty-${w}`);
      await page.goto("/runs");
      await expect(page.getByTestId("runs-page")).toBeVisible();
      await shot(page, `runs-empty-${w}`);
      expect(errors).toEqual([]);
    });

    test("offline / server error", async ({ page }) => {
      await page.goto("/cases");
      await expect(page.getByTestId("cases-page")).toBeVisible();
      await page.route("**/api/**", (route) => route.abort("internetdisconnected"));
      const errors = trackErrors(page, [/Failed to load resource|ERR_INTERNET_DISCONNECTED/]);
      await page.goto("/drugs").catch(() => undefined);
      await page.waitForTimeout(1500);
      await expect(page.locator("body")).toContainText(/offline|could not|failed|error/i);
      await shot(page, `offline-${w}`);
      expect(errors).toEqual([]);
    });

    test("unlocked: Bench run controls, Settings, Review", async ({ page }) => {
      test.skip(!CODE, "E2E_ACCESS_CODE not set");
      const errors = trackErrors(page);
      await page.goto("/?case=BOV-WD-007");
      await page.getByTestId("unlock").click();
      await page.getByLabel("Access code", { exact: true }).fill(CODE);
      await page.getByRole("button", { name: "Unlock", exact: true }).click();
      await expect(page.getByTestId("lock")).toBeVisible();
      await expect(page.getByRole("button", { name: /^Run case/ })).toBeVisible();
      await noHorizontalScroll(page);
      await shot(page, `bench-unlocked-${w}`);
      await page.goto("/settings");
      await expect(page.getByTestId("settings-page")).toBeVisible();
      await noHorizontalScroll(page);
      await shot(page, `settings-${w}`);
      await page.goto("/review");
      await expect(page.locator(".rv-item, [data-testid='review-page']").first()).toBeVisible();
      await noHorizontalScroll(page);
      await shot(page, `review-${w}`);
      await page.goto("/cases");
      await expect(page.getByRole("button", { name: "New case" })).toBeVisible();
      await shot(page, `cases-unlocked-${w}`);
      await page.getByTestId("lock").click();
      expect(errors).toEqual([]);
    });
  });
}
