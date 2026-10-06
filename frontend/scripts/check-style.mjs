// Banned-style check (Specimen v2 anti-AI rules). Scans src/ and index.html; exit 1 on any hit.
// The ONE exception: src/styles/patterns.css may use gradient functions for technical patterns
// (halftone dots, grid lines, punched-hole mask), so it is skipped entirely.
// text-shadow is allowed only in src/styles/effects.css (crisp, zero-blur misregistration).
// Run: npm run check:style
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const ALLOW_GRADIENTS = new Set(["src/styles/patterns.css"]);
const ALLOW_TEXT_SHADOW = new Set(["src/styles/effects.css"]);
// Colour literals live only in the generated tokens.
const ALLOW_COLOURS = new Set(["src/styles/tokens.css"]);

const RULES = [
  { name: "glassmorphism / backdrop-filter", re: /backdrop-filter|glassmorph/i },
  { name: "blur()", re: /blur\(/i },
  { name: "gradient function", re: /(?:linear|radial|conic|repeating-linear|repeating-radial)-gradient\s*\(/i, gradient: true },
  { name: "gradient text", re: /background-clip:\s*text/i },
  { name: "neon / glow", re: /\bneon\b|\bglow\b(?!-)/i, cssOnly: true },
  { name: "large soft shadow (blur >= 8px)", re: /box-shadow:[^;]*\b\d+px\s+\d+px\s+(?:[89]|\d{2,})px/i },
  { name: "drop-shadow filter", re: /drop-shadow\(/i },
  { name: "text-shadow outside effects.css", re: /text-shadow\s*:/i, textShadow: true },
  { name: "Inter font", re: /font-family:[^;]*["']?\bInter\b|fontsource\/inter/i },
  { name: "sparkle / AI icon", re: /sparkle|SparklesIcon|\bAiIcon\b|wand-magic/i },
  { name: "emoji", re: /[\u{1F300}-\u{1FAFF}\u{2728}\u{2B50}\u{1F004}-\u{1F251}]/u },
  { name: "parallax / floating blob", re: /parallax|\bblob\b/i },
  { name: "ad-hoc colour literal (use a token)", re: /#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab)\(/i, colour: true },
  { name: "looping animation (infinite) outside the running LED", re: /animation[^;]*\binfinite\b/i, infinite: true },
];

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else if (/\.(css|tsx?|html)$/.test(e.name)) out.push(p);
  }
  return out;
}

const files = [...walk(path.join(ROOT, "src")), path.join(ROOT, "index.html")];
let hits = 0;
for (const file of files) {
  const rel = path.relative(ROOT, file).replaceAll("\\", "/");
  if (ALLOW_GRADIENTS.has(rel)) continue;
  const lines = fs.readFileSync(file, "utf8").split("\n");
  lines.forEach((line, i) => {
    for (const r of RULES) {
      if (!r.re.test(line)) continue;
      if (r.cssOnly && !rel.endsWith(".css")) continue;
      if (r.textShadow && ALLOW_TEXT_SHADOW.has(rel)) continue;
      if (r.colour && (ALLOW_COLOURS.has(rel) || /url\(["']?data:/.test(line) || /^\s*(\/\/|\*|\/\*)/.test(line))) continue;
      // The busy LED pulse is the one sanctioned loop (runs only while a result is in flight).
      if (r.infinite && /led-pulse/.test(line)) continue;
      hits++;
      console.log(`FAIL  ${rel}:${i + 1}  [${r.name}]  ${line.trim().slice(0, 110)}`);
    }
  });
}
console.log(hits ? `\n${hits} banned-style hit(s).` : `banned-style check: clean (${files.length} files; patterns.css exempt for gradients only).`);
process.exit(hits ? 1 : 0);
