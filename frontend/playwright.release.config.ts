/* Release tests against a running production build: a Vercel deployment, or the same app run locally by
 * importing api/index.py exactly as Vercel does (see docs/DEPLOY.md, "Test a production build locally").
 *
 *   E2E_BASE_URL=http://localhost:8000 E2E_ACCESS_CODE=... npx playwright test -c playwright.release.config.ts
 *
 * Optional: E2E_BUDGET_URL and E2E_LIMIT_URL point at a second instance started with MAX_DAILY_TOKENS below
 * today's use and a low RATE_LIMIT_PER_MINUTE (e.g. 30), to check the budget cap and rate limit end to end.
 * The main instance needs a high RATE_LIMIT_PER_MINUTE (e.g. 3000): the suite makes hundreds of requests a minute. No web server is started here; the build under test must be running. */
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e-release",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  timeout: 60_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
