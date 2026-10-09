/* Every page at 1440 and 1024 wide: docs/screenshots/<page>-<width>.png */
import { expect, test } from "@playwright/test";
import path from "node:path";

const SHOTS = path.resolve(import.meta.dirname, "../../docs/screenshots");

const PAGES: { name: string; url: string; ready: string }[] = [
  { name: "bench", url: "/?case=BOV-WD-007", ready: '[data-testid="card-C0"]' },
  { name: "runs", url: "/runs", ready: '[data-testid="runs-table"]' },
  { name: "review", url: "/review", ready: ".rv-item" },
  { name: "cases", url: "/cases", ready: '[data-testid="cases-table"]' },
  { name: "drugs", url: "/drugs", ready: '[data-testid="drugs-table"]' },
  { name: "scorecard", url: "/scorecard", ready: '[data-testid="chart-dx_top1"]' },
  { name: "study", url: "/study", ready: ".ladder-svg" },
  { name: "overview", url: "/overview", ready: '[data-testid="chart-dangerous"]' },
  { name: "settings", url: "/settings", ready: '[data-testid="usage"] table' },
];

for (const width of [1440, 1024]) {
  {
    test(`all pages at ${width}`, async ({ page }) => {
      await page.setViewportSize({ width, height: width === 1440 ? 900 : 768 });
      for (const p of PAGES) {
        await page.goto(p.url);
        await expect(page.locator(p.ready).first()).toBeVisible();
        await page.waitForTimeout(450); // let entrance motion finish
        await page.screenshot({ path: path.join(SHOTS, `${p.name}-${width}.png`) });
      }
    });
  }
}
