// Dev helper: list CSS class selectors that no .tsx/.ts file references (candidates for deletion).
// Run: node scripts/find-dead-css.mjs
import fs from "node:fs";
import path from "node:path";

const SRC = path.resolve(import.meta.dirname, "../src");
const walk = (d, out = []) => {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
};
const files = walk(SRC);
const code = files.filter((f) => /\.(tsx?|html)$/.test(f)).map((f) => fs.readFileSync(f, "utf8")).join("\n") + fs.readFileSync(path.resolve(SRC, "../index.html"), "utf8");
const dead = [];
for (const f of files.filter((x) => x.endsWith(".css"))) {
  const css = fs.readFileSync(f, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/url\([^)]*\)/g, "");
  const classes = new Set([...css.matchAll(/\.([a-z][a-z0-9-]*)/gi)].map((m) => m[1]));
  for (const c of classes) {
    if (/^\d/.test(c)) continue;
    const used = new RegExp(`(["'\`\\s])${c}(["'\`\\s]|$)|className=\\{[^}]*${c}`).test(code) || code.includes(`"${c}`) || code.includes(` ${c}"`) || code.includes(`${c} `);
    if (!used) dead.push(`${path.relative(SRC, f)}  .${c}`);
  }
}
console.log(dead.length ? dead.join("\n") : "no unreferenced classes");
console.log(`\n${dead.length} candidate(s)`);
