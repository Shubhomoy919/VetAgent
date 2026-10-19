// Motion check: every animation is unique and documented, and stays inside the rules in docs/MOTION.md.
//   1. Each @keyframes name is defined exactly once, and appears in MOTION.md's keyframe registry (and vice versa).
//   2. The running LED (led-pulse) is the only infinite animation; no motion component repeats forever.
//   3. Keyframes animate only transform, opacity, clip-path, stroke-dashoffset (and the --count property).
//   4. Literal durations are 80–320 ms (CSS animations/transitions and motion `duration:` values), except the
//      LED pulse, which MOTION.md documents at 900 ms.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const SRC = join(ROOT, "src");
const MOTION_MD = join(ROOT, "..", "docs", "MOTION.md");
const ALLOWED_PROPS = new Set(["transform", "opacity", "clip-path", "stroke-dashoffset", "--count"]);
const LOOP_OK = new Set(["led-pulse"]);
const MIN_MS = 80;
const MAX_MS = 320;

function files(dir, ext) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? files(p, ext) : ext.some((e) => n.endsWith(e)) ? [p] : [];
  });
}

const problems = [];
const css = files(SRC, [".css"]);
const tsx = files(SRC, [".tsx", ".ts"]);

// 1. keyframes: unique + registered
const defined = new Map();
for (const f of css) {
  const text = readFileSync(f, "utf8");
  for (const m of text.matchAll(/@keyframes\s+([\w-]+)\s*\{/g)) {
    const name = m[1];
    if (defined.has(name)) problems.push(`@keyframes ${name} defined twice: ${defined.get(name)} and ${relative(ROOT, f)}`);
    defined.set(name, relative(ROOT, f));
    // 3. properties inside this keyframes block
    let depth = 0;
    let i = m.index + m[0].length - 1;
    const start = i;
    for (; i < text.length; i++) {
      if (text[i] === "{") depth++;
      else if (text[i] === "}" && --depth === 0) break;
    }
    const body = text.slice(start, i);
    for (const d of body.matchAll(/([\w-]+)\s*:/g)) {
      if (!ALLOWED_PROPS.has(d[1])) problems.push(`@keyframes ${name} animates "${d[1]}" (allowed: ${[...ALLOWED_PROPS].join(", ")})`);
    }
  }
}
const md = readFileSync(MOTION_MD, "utf8");
const regSection = md.split(/^## Keyframe registry/m)[1] ?? "";
const registered = new Set([...regSection.matchAll(/^\|\s*`([\w-]+)`/gm)].map((m) => m[1]));
if (registered.size === 0) problems.push("docs/MOTION.md has no '## Keyframe registry' table");
for (const name of defined.keys()) if (!registered.has(name)) problems.push(`@keyframes ${name} is not listed in MOTION.md's keyframe registry`);
for (const name of registered) if (!defined.has(name)) problems.push(`MOTION.md lists keyframes ${name}, which no stylesheet defines`);

// 2 + 4. loops and durations in CSS
for (const f of css) {
  const text = readFileSync(f, "utf8");
  for (const m of text.matchAll(/(?:^|[;{\s])(animation|animation-duration|transition|transition-duration)\s*:\s*([^;}]+)/g)) {
    const value = m[2];
    const usesLoopOk = [...LOOP_OK].some((n) => value.includes(n));
    if (/\binfinite\b/.test(value) && !usesLoopOk) problems.push(`${relative(ROOT, f)}: infinite animation "${value.trim()}"`);
    if (usesLoopOk) continue;
    // In each comma-separated animation/transition, the first time value (a literal or a --dur token) is the
    // duration and the second is the delay; token durations are 80–320 ms by definition in tokens.css.
    for (const part of value.split(",")) {
      const first = part.match(/var\(--dur[\w-]*\)|(?<![\w-])(\d*\.?\d+)(ms|s)\b/);
      if (!first || first[0].startsWith("var(")) continue;
      const ms = first[2] === "s" ? Number(first[1]) * 1000 : Number(first[1]);
      if (ms !== 0 && (ms < MIN_MS || ms > MAX_MS)) problems.push(`${relative(ROOT, f)}: ${m[1]} duration ${first[0]} outside ${MIN_MS}–${MAX_MS} ms`);
    }
  }
}

// 2 + 4. motion components
for (const f of tsx) {
  const text = readFileSync(f, "utf8");
  if (/repeat:\s*Infinity/.test(text)) problems.push(`${relative(ROOT, f)}: a motion animation repeats forever`);
  for (const d of text.matchAll(/\bduration:\s*(\d*\.?\d+)/g)) {
    const ms = Number(d[1]) * 1000;
    if (ms !== 0 && (ms < MIN_MS || ms > MAX_MS)) problems.push(`${relative(ROOT, f)}: motion duration ${d[1]} s outside ${MIN_MS}–${MAX_MS} ms`);
  }
}

if (problems.length) {
  console.error(`motion check: ${problems.length} problem(s)\n  ` + problems.join("\n  "));
  process.exit(1);
}
console.log(`motion check: clean (${defined.size} keyframes, each defined once and registered; one loop: ${[...LOOP_OK].join(", ")}; ${css.length + tsx.length} files).`);
