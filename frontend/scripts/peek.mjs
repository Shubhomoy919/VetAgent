// Dev helper: screenshot routes from a running app.  node scripts/peek.mjs <base> <outDir> <route...>
import { chromium } from "@playwright/test";
const [base, out, ...routes] = process.argv.slice(2);
const b = await chromium.launch(); const errs = [];
for (const theme of ["riso-black"]) {
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, baseURL: base });
    const p = await c.newPage(); p.on("pageerror", (e) => errs.push(e.message)); p.on("console", (m) => m.type() === "error" && errs.push(`${theme} ${m.text()}`));
  for (const r of routes) {
    await p.goto(r); await p.waitForLoadState("networkidle"); await p.waitForTimeout(900);
    const name = (r.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "bench");
    await p.screenshot({ path: `${out}/${name}-${theme}.png` });
  }
  await c.close();
}
await b.close(); console.log("console errors:", errs.length ? [...new Set(errs)].join(" | ") : "none");
