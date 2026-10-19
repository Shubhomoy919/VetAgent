// Write .br and .gz next to every compressible file in dist/, so the server can send them without
// compressing on each request (backend/app/main.py prefers .br, then .gz, by Accept-Encoding).
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { brotliCompressSync, constants, gzipSync } from "node:zlib";

const ROOT = new URL("../dist/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const EXT = /\.(js|css|html|svg|json|txt|webmanifest)$/;
let n = 0;
let before = 0;
let after = 0;

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p);
    else if (EXT.test(name)) {
      const buf = readFileSync(p);
      if (buf.length < 1024) continue;
      const br = brotliCompressSync(buf, { params: { [constants.BROTLI_PARAM_QUALITY]: 11 } });
      writeFileSync(`${p}.br`, br);
      writeFileSync(`${p}.gz`, gzipSync(buf, { level: 9 }));
      n += 1;
      before += buf.length;
      after += br.length;
    }
  }
}

walk(ROOT);
console.log(`precompress: ${n} files, ${(before / 1024).toFixed(0)} KiB → ${(after / 1024).toFixed(0)} KiB brotli`);
