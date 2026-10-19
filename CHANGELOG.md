# Changelog

All notable changes. Research prototype, not for clinical use. Consult a registered veterinarian.

## [1.1.1] - 2026-10-20

Deployment fix. The benchmark and results are unchanged (benchmark v1.0.0, content hash `b4b15a693070`).

- Vercel's import screen detects two applications (the Vite app in `frontend/` and FastAPI) and only deploys them
  as declared services. `vercel.json` now defines a `web` service (`frontend/`, Vite, `index.html` for client-side
  routes) and an `api` service (`backend/`, FastAPI `app.main:app`, `maxDuration` 300), routes `/api/(.*)` to `api`
  and everything else to `web`, and keeps the security headers at the top level. No service bindings.
- The runtime `requirements.txt` and `.python-version` (3.12) moved into `backend/`; `api/index.py` is gone.
- `vercel build` succeeds with this configuration; CI imports `app.main:app`.

## [1.1.0] - 2026-10-19

Deployment on Vercel. The benchmark is unchanged: still v1.0.0 with content hash
`b4b15a6930708f0976cb2b119f389c6d32ac321f8e2715d1751fed7c721edf07`, and the same frozen results.

### Deployment
- The whole project deploys as one Vercel project with two services (`vercel.json`): `web`, the static Vite build
  of `frontend/` from the CDN, and `api`, the FastAPI app in `backend/` (`app.main:app`) on Vercel Functions, plus
  Postgres from the Vercel Marketplace (Neon). Routes: `/api/*` to `api`, everything else to `web` (which serves
  `index.html` for client-side routes). `maxDuration` 300 s (the Hobby maximum) and security headers (CSP with
  `frame-ancestors 'none'`, nosniff, Referrer-Policy, X-Frame-Options, HSTS). Runtime dependencies and the Python
  version (3.12) live in `backend/`.
- `docs/DEPLOY.md` is now a step-by-step Vercel guide: import, settings, Marketplace Postgres, every environment
  variable, migrations and seed from your computer (PowerShell), `maxDuration`, custom domain, smoke-test checklist.
  `.env.vercel.example` lists every variable.
- Docker is gone: `Dockerfile`, `docker-compose.yml`, `docker/`, `.dockerignore`, gunicorn configuration, the
  SQLite backup script and `.env.production.example`.
- `scripts/set-live-url.ps1` puts the deployed URL in the README and the repository's About section.

### Storage
- All state is in a database: SQLAlchemy Core with `DATABASE_URL` (Postgres via psycopg 3 in production, SQLite
  locally). Tables for runs, results, traces, the answer cache, reviews, cases, drug rows, SVTG passages, saved
  settings, rate-limit counters, access-code lockout and the daily token budget. Alembic migrations.
- `python -m app.scripts.seed` (safe to run twice) loads the cases and drug table, the frozen v1.0.0 results, their
  answers into the cache (re-running a frozen case with the snapshot's model costs nothing), and the SVTG passages.
  Locally an empty database is seeded on first start.
- Cases and drug rows edited in the app are stored in the database; the files in `data/` are the seed source.

### Knowledge base
- The seed script parses your local copy of the SVTG PDF into page-numbered passages and stores them in the
  database. The PDF and the passage set are never in git or in the deployment; the function builds the BM25 index
  in memory, and pymupdf is no longer a runtime dependency.
- `/api/health` reports `index_loaded`, `chunks` and `source_pages`, and warns clearly when the passages are missing
  (the app still starts). It also reports the database engine and a missing `DATABASE_URL`.

### Runs on serverless functions
- A run is split into steps: each request runs one case through one condition and ends within the function time
  limit. The browser requests the steps in order and shows progress; the steps of a condition stream as
  server-sent events, or arrive as JSON when streaming is not available.
- A step still running at `STEP_DEADLINE_S` (240 s) is stored as "timed out" with a clear message and a Retry
  button. A reloaded page continues an unfinished run; a run without progress for `RUN_STALE_S` is marked
  interrupted. Results and the answer cache are stored in the database.

### Security
- Rate-limit counters, failed access codes, lockouts and the daily budget are stored in the database, so every
  function instance enforces them. On Vercel the client IP comes from the platform's `X-Real-IP` header.
- `npm run check:secrets` proves the built frontend contains no server-only value, key-shaped string or `VITE_`
  variable.

### Fixes
- Local development (`npm run dev`): every change made in the browser (runs, edits, Review, Settings) was refused
  as cross-origin since 1.0.0, because the Vite proxy rewrote the Host header. The proxy now keeps it.
- Development Playwright suite: waits for the API, runs in demo mode with a higher rate limit, and matches the
  current labels.

### Tests and CI
- pytest runs on a fresh database per test, on SQLite and on Postgres (`TEST_DATABASE_URL`); new tests for the seed
  (idempotent), migrations matching the schema, step runs, timeouts, resume, budget stop and the health warnings.
- CI: an import check of `api/index.py`, pytest on SQLite and on a Postgres service, migrations and the seed on a
  fresh database, the secrets scan after the frontend build.

## [1.0.0] - 2026-10-19

First public release: a read-only research site with a frozen benchmark and a frozen live result.

### Security
- Public mode is read-only. Running cases, editing or importing data, Review, Settings, Test connection and SVTG
  search need an access code (`ADMIN_ACCESS_CODE`). The code is compared as a salted scrypt hash in constant time.
  Unlocking sets a signed (HMAC-SHA256), httpOnly, Secure, SameSite=Strict session cookie.
- Lockout after repeated wrong codes: per IP (`AUTH_MAX_ATTEMPTS`, `AUTH_LOCKOUT_MINUTES`) and globally.
- Per-IP rate limit on every endpoint except health (`RATE_LIMIT_PER_MINUTE`, 429 with `Retry-After`).
- Daily live-token budget (`MAX_DAILY_TOKENS`). New runs are refused and running ones stop when it is reached,
  with a clear message. Also a cap on cases per run (`MAX_CASES_PER_RUN`).
- Security headers on every response: Content-Security-Policy (`default-src 'self'`, `frame-ancestors 'none'`),
  X-Content-Type-Options, Referrer-Policy, X-Frame-Options, Permissions-Policy, COOP, HSTS in production,
  `X-Robots-Tag: noindex`.
- CORS only for `ALLOWED_ORIGINS`; cross-origin writes refused.
- Request bodies size-limited (`MAX_BODY_BYTES`, also for chunked uploads); every text field and list has a
  maximum length; imports are capped at 1,000 records.
- No stack traces in responses (500s return a reference ID). Validation errors never echo input. API docs are
  off in production.
- Logs are redacted at record creation (configured secrets and anything shaped like an API key); the access log
  has no query strings or bodies.
- Secret scan of the full git history with gitleaks: no leaks.

### Research integrity
- Benchmark frozen as **v1.0.0** with a content hash
  (`b4b15a6930708f0976cb2b119f389c6d32ac321f8e2715d1751fed7c721edf07`), shown in `/api/health`, on the Overview
  and in every export. Data edited after the freeze reads `1.0.0+modified`.
- Every run records provider, model, prompt version, temperature, benchmark version, benchmark hash and date. The
  Scorecard shows them, and the CSV/JSON exports carry them with the disclaimer.
- Frozen results snapshot `snapshots/v1.0.0/run.json` (one complete live run, 145/145 answers) with a SHA-256
  file. It loads automatically into an empty database, and `app.scripts.snapshot verify` re-scores it.
- Demo data never appears in production: demo runs are refused, filtered out of every page and export, and
  deleted at startup.
- The SVTG PDF is no longer in the repository or the image, and is never served. Visitors see only passages cited
  by stored or gold answers, with page numbers and a link to DAHD's copy.
- UNVERIFIED tags now sit in the second column of the Cases and Drug tables, visible at every width.

### Deployment
- FastAPI serves the built frontend, so one service handles both. Static assets are pre-compressed (Brotli and
  gzip) with immutable caching; API responses are gzipped; SSE is never buffered.
- Multi-stage `Dockerfile` (node build → Python deps → slim runtime), non-root user, `HEALTHCHECK` on
  `/api/health`, gunicorn with one uvicorn worker and graceful shutdown (an active run is cancelled and recorded;
  runs cut off by a crash are marked `interrupted`).
- `docker-compose.yml` with a persistent volume for the database and data, the PDF mounted read-only.
- `.env.production.example` documenting every variable; `docs/DEPLOY.md` for Render, Railway and Fly.io.
- `app.scripts.backup` (SQLite online backup with integrity check and rotation), `app.scripts.benchmark`,
  `app.scripts.snapshot`. `DATA_DIR` makes the data location configurable.
- `/api/health` reports version, environment, benchmark version and hash, `pdf_loaded`, `key_present`, mode
  (public/admin), LLM mode (live/demo) and database status.

### Interface
- Access-code prompt (page gate for Review and Settings, dialog from the top bar and the `R` shortcut), read-only
  notes, Lock/Unlock in the top bar, budget readout in the run bar, offline banner.
- Sentence case throughout (stamps excepted), one number format (`1,234`), consistent action names
  ("Export CSV", "Print report", "Cancel run"), one wording for run states.
- Page titles per route, favicon from the pink ink mark, Open Graph image from the Overview hero,
  `noindex` robots meta and `robots.txt`.
- Accessibility: screen-reader descriptions for verdict stamps; focus returns to the trigger when the access
  dialog closes; keyboard walkthrough tested.
- Performance: route-level code splitting (main bundle 722 kB → 470 kB), preloaded critical fonts (Study CLS
  0.050 → 0.004).
- Removed the stale `scripts/peek.mjs` dev helper.

### Fixes
- Settings can be saved when the SVTG PDF is absent. Only a change of the PDF path is checked against the file.

### Project
- README rewritten: motivation, research questions, metric definitions, results generated from the snapshot with
  Wilson intervals, architecture diagram, setup for Windows, macOS and Linux, reproducibility and limitations.
- `CONTRIBUTING.md`, `SECURITY.md` (private vulnerability reporting), issue and pull-request templates.
- GitHub Actions CI on every push and pull request: benchmark and snapshot checks, pytest, tsc, ESLint, style,
  contrast and motion checks, production build.
- A `commit-msg` hook (`scripts/install-hooks.sh` / `.ps1`) that removes tool-attribution lines from commit
  messages.

### Tests
- `backend/tests/test_security.py` (41 tests): read-only mode, access code, lockout, sessions, rate limit,
  budget, case cap, demo exclusion, headers, body limits, SVTG gating, redaction, run metadata, snapshot
  reproduction.
- `npm run check:motion`: every keyframe defined once and listed in MOTION.md, the LED pulse is the only loop,
  only allowed properties, durations 80–320 ms.
- Playwright release suite (`playwright.release.config.ts`) against a production build: public browsing, blocked
  runs, a live run through C0–C4, Scorecard and CSV provenance, budget cap, rate limit, keyboard walkthrough, and
  every page and state at 1440/1024/768 px.

## [0.x] - 2026-10-03 to 2026-10-18

Milestones M1–M8 (skeleton, data, agent, Bench, Scorecard, data pages, Runs/Review/Study/Overview/Settings,
polish) and the black-and-pink design system. See the git history.
