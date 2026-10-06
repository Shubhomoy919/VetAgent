// WCAG contrast check for the Specimen v2 tokens (src/styles/tokens.css), both themes.
// Text tokens must reach 4.5:1 on every background; the focus ring must reach 3:1 (non-text UI).
// Exit code 1 if anything fails.  Run: npm run check:contrast
import fs from "node:fs";
import path from "node:path";

const css = fs.readFileSync(path.resolve(import.meta.dirname, "../src/styles/tokens.css"), "utf8");

function block(selectorStart) {
  const i = css.indexOf(selectorStart);
  if (i < 0) throw new Error(`theme block not found: ${selectorStart}`);
  const body = css.slice(css.indexOf("{", i) + 1, css.indexOf("\n}", i));
  const vars = {};
  for (const m of body.matchAll(/--([\w-]+):\s*([^;]+);/g)) vars[m[1]] = m[2].trim();
  return vars;
}

const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
const hex = (c) => "#" + c.map((x) => Math.round(Math.min(Math.max(x, 0), 1) * 255).toString(16).padStart(2, "0")).join("");

function resolve(vars, value) {
  value = value.trim();
  if (/^#[0-9a-f]{6}$/i.test(value)) return value.toLowerCase();
  const ref = value.match(/^var\(--([\w-]+)\)$/);
  if (ref) return resolve(vars, vars[ref[1]]);
  const mix = value.match(/^color-mix\(in srgb,\s*(.+?)\s+(\d+)%,\s*(.+)\)$/);
  if (mix) {
    const a = rgb(resolve(vars, mix[1]));
    const b = rgb(resolve(vars, mix[3]));
    const p = Number(mix[2]) / 100;
    return hex(a.map((x, i) => x * p + b[i] * (1 - p)));
  }
  throw new Error(`cannot resolve ${value}`);
}

const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lum = (h) => rgb(h).reduce((s, c, i) => s + [0.2126, 0.7152, 0.0722][i] * lin(c), 0);
const ratio = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};

const BACKGROUNDS = ["bg", "surface", "raised", "surface-sunk"];
const TEXT = [
  "ink", "ink-2",
  "indigo-text", "cyan-text", "peacock-text", "marigold-text", "riso-text", "vermilion-text", "madder-text",
  "leaf-text", "terracotta-text", "ochre-text", "forest-text",
  "c0-text", "c1-text", "c2-text", "c3-text", "c4-text",
];
// Text drawn on filled areas: buttons, the sidebar and top bar, condition blocks (Bone & Block).
const ON_FILL = [
  ["on-accent", "indigo"], ["on-accent", "ink"], ["on-accent", "vermilion-text"], ["on-marigold", "marigold"],
  ["sidebar-ink", "sidebar"], ["sidebar-ink-2", "sidebar"], ["topbar-ink", "topbar-bg"], ["topbar-accent", "topbar-bg"],
];
const BLOCKS = ["c0-block", "c1-block", "c2-block", "c3-block", "c4-block"];

let failures = 0;
const THEMES = [
  ["cyanotype", ':root,\n:root[data-theme="cyanotype"]'],
  ["bone-block", ':root[data-theme="bone-block"]'],
  ["kalamkari", ':root[data-theme="kalamkari"]'],
];
for (const [theme, sel] of THEMES) {
  const v = block(sel);
  const rows = [];
  for (const fg of TEXT) {
    const worst = Math.min(...BACKGROUNDS.map((bg) => ratio(resolve(v, `var(--${fg})`), resolve(v, `var(--${bg})`))));
    rows.push({ pair: `${fg} on bg/surface/raised/sunk`, need: 4.5, worst });
  }
  if (theme === "bone-block") for (const bl of BLOCKS) rows.push({ pair: `on-block (bone) on ${bl}`, need: 4.5, worst: ratio(resolve(v, "var(--on-block)"), resolve(v, `var(--${bl})`)) });
  for (const [fg, bg] of ON_FILL) rows.push({ pair: `${fg} on ${bg}`, need: 4.5, worst: ratio(resolve(v, `var(--${fg})`), resolve(v, `var(--${bg})`)) });
  const focus = Math.min(...BACKGROUNDS.map((bg) => ratio(resolve(v, "var(--focus)"), resolve(v, `var(--${bg})`))));
  rows.push({ pair: "focus ring (riso) on backgrounds", need: 3, worst: focus });

  console.log(`\n${theme.toUpperCase()}`);
  for (const r of rows) {
    const ok = r.worst >= r.need;
    if (!ok) failures++;
    console.log(`  ${ok ? "PASS" : "FAIL"}  ${r.worst.toFixed(2).padStart(5)}:1  (needs ${r.need})  ${r.pair}`);
  }
}
console.log(failures ? `\n${failures} contrast failure(s)` : "\nAll text, chrome and focus pairs pass WCAG AA in all three themes.");
process.exit(failures ? 1 : 0);
