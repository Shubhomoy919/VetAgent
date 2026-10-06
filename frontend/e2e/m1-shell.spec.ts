import { expect, test, type ConsoleMessage } from "@playwright/test";
import path from "node:path";

const SHOTS = path.resolve(import.meta.dirname, "../../docs/screenshots");

test("health endpoint through the Vite proxy is this project's backend", async ({ request }) => {
  const res = await request.get("/api/health");
  expect(res.ok()).toBe(true);
  const body = await res.json();
  for (const key of ["configured_provider", "mode", "pdf_loaded", "pages", "chunks", "key_present", "model", "counts"]) {
    expect(body).toHaveProperty(key);
  }
  expect(typeof body.key_present).toBe("boolean");
});

test("/ opens the Bench shell with zero console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (msg: ConsoleMessage) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));

  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");

  await expect(page.getByTestId("bench")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: "Bench" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Bench" })).toHaveClass(/active/);
  await expect(page.getByText("Research prototype — not for clinical use. Consult a registered veterinarian.")).toBeVisible();

  const health = await (await page.request.get("/api/health")).json();
  await expect(page.getByTestId("model-id")).toHaveText(health.model);
  if (health.mode === "demo") {
    await expect(page.getByTestId("demo-banner")).toHaveText("Demo mode: sample responses, not live model output");
  }

  // All five conditions render with their ablation ladders.
  for (const id of ["C0", "C1", "C2", "C3", "C4"]) {
    await expect(page.locator(`.deck-tab[data-cond="${id}"]`)).toBeVisible();
  }

  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.waitForTimeout(400); // let entrance motion settle before the screenshot
  await page.screenshot({ path: path.join(SHOTS, "m1-bench-1440-light.png") });

  await page.getByTestId("theme-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.screenshot({ path: path.join(SHOTS, "m1-bench-1440-dark.png") });

  // Theme choice persists across reload.
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  expect(errors, `console errors:\n${errors.join("\n")}`).toEqual([]);
});
