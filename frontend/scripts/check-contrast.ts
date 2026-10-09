// WCAG contrast check for every text/background pair the UI uses (Riso Black, the only theme).
// Normal text >= 4.5:1, large text and graphical marks >= 3:1. Exit 1 on any failure.
// Run: npm run check:contrast   (Node runs this TypeScript file directly)
import fs from "node:fs";
import path from "node:path";

const css = fs.readFileSync(path.resolve(import.meta.dirname, "../src/styles/tokens.css"), "utf8");

type Vars = Record<string, string>;

function block(selectorStart: string): Vars {
  const i = css.indexOf(selectorStart);
  if (i < 0) throw new Error(`theme block not found: ${selectorStart}`);
  const body = css.slice(css.indexOf("{", i) + 1, css.indexOf("\n}", i));
  const vars: Vars = {};
  for (const m of body.matchAll(/--([\w-]+):\s*([^;]+);/g)) vars[m[1] as string] = (m[2] as string).trim();
  return vars;
}

const rgb = (h: string): number[] => {
  const x = h.length === 4 ? `#${h[1]}${h[1]}${h[2]}${h[2]}${h[3]}${h[3]}` : h;
  return [1, 3, 5].map((i) => parseInt(x.slice(i, i + 2), 16) / 255);
};
const hex = (c: number[]): string => "#" + c.map((x) => Math.round(Math.min(Math.max(x, 0), 1) * 255).toString(16).padStart(2, "0")).join("");

function resolve(v: Vars, value: string): string {
  value = value.trim();
  if (/^#[0-9a-f]{3}([0-9a-f]{3})?$/i.test(value)) return value.toLowerCase();
  const ref = value.match(/^var\(--([\w-]+)\)$/);
  if (ref) {
    const next = v[ref[1] as string];
    if (next === undefined) throw new Error(`undefined token --${ref[1]}`);
    return resolve(v, next);
  }
  const mix = value.match(/^color-mix\(in srgb,\s*(.+?)\s+(\d+)%,\s*(.+)\)$/);
  if (mix) {
    const a = rgb(resolve(v, mix[1] as string));
    const b = rgb(resolve(v, mix[3] as string));
    const p = Number(mix[2]) / 100;
    return hex(a.map((x, i) => x * p + (b[i] as number) * (1 - p)));
  }
  throw new Error(`cannot resolve ${value}`);
}

const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lum = (h: string) => rgb(h).reduce((s, c, i) => s + ([0.2126, 0.7152, 0.0722][i] as number) * lin(c), 0);
const ratio = (a: string, b: string) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p) as [number, number];
  return (x + 0.05) / (y + 0.05);
};

type Pair = { fg: string; bg: string; need: 4.5 | 3; use: string };

const GROUNDS = ["bg", "surface", "raised", "surface-sunk"];
const TEXT_ON_GROUND = [
  "text", "text-body", "text-muted", "text-dim",
  "c0-text", "c1-text", "c2-text", "c3-text", "c4-text",
  "safe-text", "unsafe-text", "caution-text", "info-text", "running-text", "accent-text",
];
// Inks that carry --text-on-ink (buttons, nav tag, lit triage, chips, ladder cards). Madder never does.
const INK_FILLS = ["ink-pink", "ink-sunflower", "ink-orange", "ink-cornflower", "ink-violet", "ink-mint", "info", "safe", "running", "nav-active-bg", "c0", "c1", "c2", "c3", "c4"];

const PAIRS: Pair[] = [
  ...TEXT_ON_GROUND.flatMap((fg) => GROUNDS.map((bg) => ({ fg, bg, need: 4.5 as const, use: "text on page / panel" }))),
  { fg: "paper-text", bg: "paper", need: 4.5, use: "paper sheet text" },
  { fg: "paper-muted", bg: "paper", need: 4.5, use: "paper sheet secondary text" },
  { fg: "hero-text", bg: "hero-bg", need: 4.5, use: "hero sheet text" },
  { fg: "hero-text-2", bg: "hero-bg", need: 4.5, use: "hero sheet secondary text" },
  ...INK_FILLS.map((bg) => ({ fg: "text-on-ink", bg, need: 4.5 as const, use: "text on an ink fill" })),
  { fg: "text", bg: "unsafe-tint", need: 4.5, use: "emergency triage / danger hover (madder tint)" },
  { fg: "sidebar-ink", bg: "sidebar", need: 4.5, use: "sidebar" },
  { fg: "sidebar-ink-2", bg: "sidebar", need: 4.5, use: "sidebar labels" },
  { fg: "topbar-ink", bg: "topbar-bg", need: 4.5, use: "top bar" },
  { fg: "topbar-ink-2", bg: "topbar-bg", need: 4.5, use: "top bar labels" },
  { fg: "topbar-accent", bg: "readout-bg", need: 4.5, use: "top bar readouts" },
  { fg: "topbar-ink-2", bg: "readout-bg", need: 4.5, use: "top bar readout labels" },
  { fg: "meter-ink", bg: "meter-off", need: 4.5, use: "triage strip labels" },
  // Large text and graphical marks (3:1)
  ...["c0-paper", "c1-paper", "c2-paper", "c3-paper", "c4-paper", "safe-paper", "unsafe-paper"].map((fg) => ({ fg, bg: "paper", need: 3 as const, use: "marks / large labels on paper" })),
  ...["c0", "c1", "c2", "c3", "c4", "unsafe", "safe"].map((fg) => ({ fg, bg: "bg", need: 3 as const, use: "chart marks on the ground" })),
  ...GROUNDS.map((bg) => ({ fg: "focus-ring", bg, need: 3 as const, use: "focus ring" })),
];

const THEMES: [string, string][] = [["riso-black", ":root"]];

let failures = 0;
let checked = 0;
for (const [theme, sel] of THEMES) {
  const v = block(sel);
  console.log(`\n${theme.toUpperCase()}`);
  let worstText = Infinity;
  for (const p of PAIRS) {
    const r = ratio(resolve(v, `var(--${p.fg})`), resolve(v, `var(--${p.bg})`));
    checked++;
    if (p.need === 4.5) worstText = Math.min(worstText, r);
    if (r < p.need) {
      failures++;
      console.log(`  FAIL  ${r.toFixed(2)}:1  needs ${p.need}  --${p.fg} on --${p.bg}  (${p.use})`);
    }
  }
  console.log(`  ${PAIRS.length} pairs checked · lowest text ratio ${worstText.toFixed(2)}:1`);
}
console.log(failures ? `\n${failures} contrast failure(s) of ${checked}` : `\nAll ${checked} pairs pass (4.5:1 text, 3:1 large text and marks) in Riso Black.`);
process.exit(failures ? 1 : 0);
