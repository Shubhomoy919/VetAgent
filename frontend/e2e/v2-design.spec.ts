import { expect, test } from "@playwright/test";

// Case dossier, compare diffs, instrument meter, switchboards, semantic tokens.


test("case dossier shows the full case, gold answer and past results", async ({ page, request }) => {
  // make sure the case has at least one stored result
  const runId = (await (await request.post("/api/runs", { data: { case_ids: ["BOV-WD-007"], conditions: ["C0"], interview: false, force: false } })).json()).run_id as string;
  await expect.poll(async () => (await (await request.get(`/api/runs/${runId}`)).json()).status, { timeout: 60_000 }).not.toBe("running");

  await page.goto("/?case=BOV-WD-007");
  await page.getByTestId("open-dossier").click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toContainText("Case dossier");
  await expect(drawer).toContainText("Owner narrative");
  await expect(drawer.getByTestId("gold-answer")).toBeVisible();
  await expect(drawer.getByTestId("dossier-results").locator("tbody tr").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("dossier-results")).toHaveCount(0);
});

test("compare mode marks differing answers and scrolls cards together", async ({ page }) => {
  await page.goto("/?case=BOV-WD-007");
  await expect(page.getByTestId("card-C0")).toBeVisible();
  await page.getByRole("button", { name: "Compare" }).click();
  await expect(page.locator('.deck[data-mode="compare"]')).toBeVisible();
  const cards = page.locator('.deck[data-mode="compare"] .ccard');
  await expect(cards).toHaveCount(2);
  // C0 and C4 have stored answers for this case and they disagree (diagnosis wording, drug status, ...).
  await expect(page.locator('.deck[data-mode="compare"] .ccard-answer')).toHaveCount(2);
  expect(await page.locator(".ccard [data-diff]").count()).toBeGreaterThanOrEqual(1);

  // Scroll sync: scrolling one card moves the other to the same relative position (when they can scroll).
  const synced = await page.evaluate(async () => {
    const [a, b] = [...document.querySelectorAll<HTMLElement>('.deck[data-mode="compare"] .ccard')];
    if (!a || !b || a.scrollHeight <= a.clientHeight || b.scrollHeight <= b.clientHeight) return "not-scrollable";
    a.scrollTop = a.scrollHeight;
    await new Promise((r) => setTimeout(r, 120));
    return b.scrollTop > 0 ? "synced" : "not-synced";
  });
  expect(synced).not.toBe("not-synced");
});

test("running a case lights the meter and LEDs", async ({ page }) => {
  await page.goto("/?case=CAP-001");
  await page.getByText("Force re-run").click();
  await page.getByRole("button", { name: /Run case/ }).click();
  const meter = page.getByRole("progressbar", { name: "Run progress" });
  await expect(meter).toBeVisible();
  await expect(meter.locator(".meter-seg")).toHaveCount(5);
  await expect(page.getByTestId("run-status")).toHaveText("Done 5/5", { timeout: 90_000 });
  await expect(meter.locator('.meter-seg[data-state="done"], .meter-seg[data-state="error"]')).toHaveCount(5);
  await expect(page.locator('.deck-tab .led[data-state="ok"], .deck-tab .led[data-state="danger"], .deck-tab .led[data-state="done"]')).toHaveCount(5);
});

test("ablation ladder renders as toggles with the right on-states", async ({ page }) => {
  await page.goto("/study");
  await expect(page.locator(".lf-track.on")).toHaveCount(10); // 0+1+2+3+4 switches on
  await page.goto("/scorecard");
  const c4 = page.locator('.sc-legend-item[data-cond="C4"] .ladder-step[data-on="true"]');
  await expect(c4).toHaveCount(4);
});

test("tokens: black ground, pink accent and the semantic set are defined", async ({ page }) => {
  await page.goto("/overview");
  {
    const v = await page.evaluate(() => {
      const s = getComputedStyle(document.documentElement);
      return ["--bg", "--ink-pink", "--accent-text", "--focus-ring", "--safe", "--unsafe-text", "--c0", "--c4-text"].map((k) => s.getPropertyValue(k).trim());
    });
    for (const x of v) expect(x).not.toBe("");
  }
});
