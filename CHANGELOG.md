# Changelog

All notable changes. Research prototype, not for clinical use. Consult a registered veterinarian.

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
