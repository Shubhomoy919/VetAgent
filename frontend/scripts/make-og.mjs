// Build the social preview (public/og.png, 1200×630) from the Overview hero, and the 180 px touch icon from
// the favicon. Run against a running production build:  node scripts/make-og.mjs http://localhost:8000
import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";

const base = process.argv[2] ?? "http://localhost:8000";
const pub = new URL("../public/", import.meta.url);
const browser = await chromium.launch();

// og.png: the Overview hero (title, question, figures) without the app chrome.
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, reducedMotion: "reduce" });
await page.goto(`${base}/overview`);
await page.getByTestId("overview-page").waitFor();
await page.addStyleTag({ content: ".sidebar,.topbar,.footer,.demo-banner,.ov-section{display:none!important}.shell{grid-template-columns:1fr!important}" });
await page.setViewportSize({ width: 1200, height: 630 });
await page.waitForTimeout(400);
await page.screenshot({ path: new URL("og.png", pub).pathname.replace(/^\/([A-Za-z]:)/, "$1"), clip: { x: 0, y: 0, width: 1200, height: 630 } });

// apple-touch-icon.png: the pink ink mark on black.
const icon = await browser.newPage({ viewport: { width: 180, height: 180 } });
const svg = readFileSync(new URL("favicon.svg", pub), "utf8");
await icon.setContent(`<html><body style="margin:0;background:#000">${svg.replace("<svg ", '<svg width="180" height="180" ')}</body></html>`);
await icon.screenshot({ path: new URL("apple-touch-icon.png", pub).pathname.replace(/^\/([A-Za-z]:)/, "$1") });

await browser.close();
console.log("wrote public/og.png and public/apple-touch-icon.png");
