import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: {
    command: "npm --prefix .. run dev",
    // Wait for the API through the proxy, not just Vite: the first start seeds the local database.
    url: "http://localhost:5173/api/health",
    reuseExistingServer: true,
    timeout: 60_000,
    // Demo answers only (no API spend), and a rate limit above the suite's few hundred requests a minute.
    env: { LLM_PROVIDER: "demo", RATE_LIMIT_PER_MINUTE: "5000" },
  },
});
