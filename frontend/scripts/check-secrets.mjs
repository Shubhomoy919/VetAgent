// Prove that no secret reaches the browser: scan the built frontend (dist/) for
//   1. the values of the server-only variables, read from the environment and the repo-root .env file,
//   2. anything shaped like an API key, a private key or a database URL,
// and the source for VITE_-prefixed variables (Vite inlines those into the bundle).
// Values are never printed, only the variable name and the file. Exit 1 on any finding.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const here = (p) => new URL(p, import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const DIST = here("../dist/");
const SRC = here("../src/");
const ENV_FILE = here("../../.env");

const SECRET_VARS = ["GEMINI_API_KEY", "OPENAI_API_KEY", "ADMIN_ACCESS_CODE", "SESSION_SECRET", "DATABASE_URL",
  "DATABASE_URL_UNPOOLED", "POSTGRES_URL", "POSTGRES_PASSWORD", "PGPASSWORD"];
const PATTERNS = [
  ["Google API key", /AIza[0-9A-Za-z_-]{35}/],
  ["OpenAI-style key", /\bsk-[A-Za-z0-9_-]{20,}/],
  ["private key", /-----BEGIN [A-Z ]*PRIVATE KEY-----/],
  ["database URL", /\bpostgres(?:ql)?(?:\+\w+)?:\/\/[^\s"'`]+@/],
];

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
}

function envFileValues() {
  if (!existsSync(ENV_FILE)) return {};
  const out = {};
  for (const line of readFileSync(ENV_FILE, "utf8").split(/\r?\n/)) {
    const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/.exec(line);
    if (m) out[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
  return out;
}

if (!existsSync(DIST)) {
  console.error("check-secrets: no dist/ folder. Run the build first: npm run build");
  process.exit(2);
}

const fromFile = envFileValues();
const values = SECRET_VARS.map((name) => [name, process.env[name] || fromFile[name] || ""]).filter(([, v]) => v.length >= 6);
const files = walk(DIST).filter((p) => !/\.(br|gz|png|jpe?g|woff2?|ico)$/.test(p));
const findings = [];

for (const file of files) {
  const text = readFileSync(file, "utf8");
  const rel = relative(DIST, file);
  for (const [name, value] of values) if (text.includes(value)) findings.push(`${rel}: value of ${name}`);
  for (const [label, re] of PATTERNS) if (re.test(text)) findings.push(`${rel}: something shaped like a ${label}`);
}
for (const file of walk(SRC).filter((p) => /\.(ts|tsx)$/.test(p))) {
  if (/import\.meta\.env\.VITE_/.test(readFileSync(file, "utf8"))) findings.push(`src/${relative(SRC, file)}: uses a VITE_ variable`);
}

console.log(`check-secrets: scanned ${files.length} built files and the source; compared against ${values.length} ` +
  `server-only value(s) present here (${values.map(([n]) => n).join(", ") || "none set"}) and ${PATTERNS.length} key patterns.`);
if (findings.length) {
  console.error("check-secrets: FOUND\n  " + findings.join("\n  "));
  process.exit(1);
}
console.log("check-secrets: clean (no secret values, key-shaped strings or VITE_ variables in the frontend).");
