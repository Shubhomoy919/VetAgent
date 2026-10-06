// Specimen v2 screenshots -> docs/screenshots/v2/
//   node scripts/shoot-v2.mjs <pagesBaseUrl> <runBaseUrl>
// pagesBaseUrl: app used for the static page shots (read-only page views).
// runBaseUrl:   app used for the mid-run Bench shot (should be a DEMO-mode backend: it starts a run).
import fs from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";

const PAGES_URL = process.argv[2] ?? "http://localhost:5173";
const RUN_URL = process.argv[3] ?? PAGES_URL;
const OUT = path.resolve(import.meta.dirname, "../../docs/screenshots/v2");
fs.mkdirSync(OUT, { recursive: true });

const PAGES = [
  ["bench", "/?case=BOV-WD-007"],
  ["runs", "/runs"],
  ["review", "/review"],
  ["cases", "/cases"],
  ["drugs", "/drugs"],
  ["scorecard", "/scorecard"],
  ["study", "/study"],
  ["overview", "/overview"],
  ["settings", "/settings"],
];
const SIZES = [
  [1440, 900],
  [1024, 768],
];

const errors = [];
const shots = [];
const browser = await chromium.launch();

async function context(base, theme, w, h, coach = "done") {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: theme, baseURL: base });
  await ctx.addInitScript(
    ([t, c]) => {
      try {
        localStorage.setItem("vab.theme", t);
        if (c) localStorage.setItem("vab.coach", c);
        else localStorage.removeItem("vab.coach");
      } catch {
        /* ignore */
      }
    },
    [theme, coach],
  );
  return ctx;
}

function track(page, label) {
  page.on("console", (m) => m.type() === "error" && errors.push(`${label}: ${m.text()}`));
  page.on("pageerror", (e) => errors.push(`${label}: ${e.message}`));
}

async function save(page, name) {
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file });
  shots.push(path.relative(path.resolve(OUT, "../../.."), file).replaceAll("\\", "/"));
}

// 1. Every page, both sizes, both themes.
for (const theme of ["light", "dark"]) {
  for (const [w, h] of SIZES) {
    const ctx = await context(PAGES_URL, theme, w, h);
    const page = await ctx.newPage();
    track(page, `${theme} ${w}`);
    for (const [name, route] of PAGES) {
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(900);
      await save(page, `${name}-${w}-${theme}`);
    }
    await ctx.close();
  }
}

// 2. Feature close-ups (1440 light): dossier, compare mode, coach marks.
{
  const ctx = await context(PAGES_URL, "light", 1440, 900);
  const page = await ctx.newPage();
  track(page, "features");
  await page.goto("/?case=BOV-WD-007");
  await page.waitForLoadState("networkidle");
  await page.getByTestId("open-dossier").click();
  await page.waitForTimeout(700);
  await save(page, "feature-dossier-1440-light");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Compare" }).click();
  await page.waitForTimeout(900);
  await save(page, "feature-compare-1440-light");
  await ctx.close();

  const ctx2 = await context(PAGES_URL, "dark", 1440, 900, null);
  const p2 = await ctx2.newPage();
  track(p2, "coach");
  await p2.goto("/?case=BOV-WD-007");
  await p2.waitForLoadState("networkidle");
  await p2.getByRole("button", { name: "Next" }).click();
  await p2.waitForTimeout(500);
  await save(p2, "feature-coach-1440-dark");
  await ctx2.close();
}

// 3. Mid-run Bench (demo backend): force a run and capture while results are landing.
for (const theme of ["light", "dark"]) {
  const ctx = await context(RUN_URL, theme, 1440, 900);
  const page = await ctx.newPage();
  track(page, `midrun ${theme}`);
  await page.goto("/?case=CAN-013");
  await page.waitForLoadState("networkidle");
  await page.getByText("Force re-run").click();
  await page.getByRole("button", { name: /Run case/ }).click();
  // wait until at least one result has landed but the run is still going
  await page.waitForFunction(() => {
    const t = document.querySelector('[data-testid="run-status"]')?.textContent ?? "";
    const m = t.match(/Running (\d+)\/(\d+)/);
    return m && Number(m[1]) >= 2;
  }, null, { timeout: 60_000 });
  await page.waitForTimeout(250);
  await save(page, `bench-midrun-1440-${theme}`);
  await page.waitForFunction(() => /Done/.test(document.querySelector('[data-testid="run-status"]')?.textContent ?? ""), null, { timeout: 90_000 });
  await page.waitForTimeout(900);
  await save(page, `bench-afterrun-1440-${theme}`);
  await ctx.close();
}

await browser.close();
console.log(shots.join("\n"));
console.log(`\n${shots.length} screenshots`);
console.log(errors.length ? `console errors:\n${errors.join("\n")}` : "console errors: none");
