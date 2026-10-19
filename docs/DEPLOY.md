# Deploying VetAgentBench-IN on Vercel

One Vercel project with two [services](https://vercel.com/docs/services) (defined in `vercel.json`) serves
everything on one domain:

- **`web`**: the static Vite build of `frontend/`, from Vercel's CDN, for every path except `/api/*`
  (unknown paths get `index.html`, so client-side routes work);
- **`api`**: the FastAPI app in `backend/` (entrypoint `app.main:app`), run as Vercel Functions, for every
  `/api/*` request; it receives the original path, e.g. `/api/health`;
- the **database**: Postgres from the Vercel Marketplace (Neon), holding runs, results, the benchmark data, the
  SVTG passages, rate-limit counters and the daily token budget.

The public site is read-only and shows the frozen v1.0.0 results without spending API credits. Running cases,
editing data, Review and Settings need the access code.

Research prototype, not for clinical use. Consult a registered veterinarian.

| Anyone (read-only) | Needs `ADMIN_ACCESS_CODE` |
|---|---|
| Overview, Scorecard, Cases, Drug table, Runs, Study design | Running cases (Bench run bar, `R`) |
| The Bench with the stored results of a completed run | Editing or importing cases and drug rows |
| Cited SVTG passages, with page numbers and a link to DAHD's copy | Review (veterinarian ratings) |
| CSV / JSON exports (with disclaimer, benchmark hash, model, prompt, temperature) | Settings, Test connection, SVTG search |

The SVTG PDF is never committed, deployed or served. The seed script reads your local copy and stores
page-numbered passages in the database; visitors see only passages that a stored answer or gold answer cites.

## Before you start

- A Vercel account (Hobby is enough) connected to GitHub, and this repository on GitHub.
- On your computer: this repository, Python 3.11+ with `npm run setup` done (it installs Alembic and pymupdf into
  `.venv`), and the SVTG PDF from DAHD:
  <https://dahd.gov.in/sites/default/files/2024-10/StandardVeterinaryTreatment.pdf>
- Two random secrets:

  ```powershell
  .venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(24))"   # ADMIN_ACCESS_CODE
  .venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"   # SESSION_SECRET
  ```

## 1. Import the repository

Vercel dashboard → **Add New… → Project** → pick the `VetAgent` GitHub repository → **Import**. Do not deploy
yet if Vercel offers to; the database and variables come first (a deployment without them starts, but
`/api/health` reports the missing database).

## 2. Root directory and framework settings

On the import screen (later: **Settings → Build and Deployment**):

| Setting | Value |
|---|---|
| Root Directory | `./` (the repository root, where `vercel.json` is) |
| Framework / build settings | nothing to set: Vercel reads the services from `vercel.json` |
| Node.js Version | 22.x or 24.x |

The import screen lists the two services it found in `vercel.json`:

| Service | Root | What Vercel does |
|---|---|---|
| `web` | `frontend/` | Vite: `npm ci`, `npm run build`, serves `dist/` from the CDN |
| `api` | `backend/` | FastAPI: installs `backend/requirements.txt` with Python 3.12 (`backend/.python-version`), runs `app.main:app` |

Public routing, most specific first: `/api/(.*)` → `api`, then `/(.*)` → `web`. There are no service bindings:
the browser calls the API with same-origin `/api/...` URLs, and the API calls only Gemini and Postgres.

## 3. Add Postgres from the Marketplace

Project → **Storage → Create Database → Neon** (Marketplace) → choose a region close to your function's region
(Settings → Functions → Function Region; the two should match) → **Connect** to this project for Production and
Preview. The integration adds `DATABASE_URL` (pooled, used by the app) and `DATABASE_URL_UNPOOLED` (direct,
used for migrations and the seed) to the project's environment variables.

## 4. Environment variables

Project → **Settings → Environment Variables**. All of them are server-only: the Python function reads them;
the browser never sees them. **Never prefix any of them with `VITE_`**: Vite copies `VITE_` variables into the
public JavaScript bundle (`npm --prefix frontend run check:secrets` fails the build check if one is used). The
full list with comments is in [`.env.vercel.example`](../.env.vercel.example).

| Variable | Required | Description |
|---|---|---|
| `APP_ENV` | yes | `production`: read-only public mode, demo results hidden, API docs off, HSTS |
| `DATABASE_URL` | yes (Neon adds it) | Pooled Postgres URL used by the app |
| `DATABASE_URL_UNPOOLED` | yes (Neon adds it) | Direct Postgres URL for migrations and the seed script |
| `ADMIN_ACCESS_CODE` | for runs and edits | The access code; empty = permanently read-only site |
| `SESSION_SECRET` | yes | 32+ random characters; signs the session cookie |
| `ALLOWED_ORIGINS` | recommended | Your site's origin(s), comma-separated, e.g. `https://vetagent.vercel.app` |
| `LLM_PROVIDER` | for live runs | `gemini` (or `openai_compatible`) |
| `GEMINI_API_KEY` | for live runs | Without it, runs are disabled and only stored results show |
| `GEMINI_MODEL` | for live runs | `gemini-3.5-flash-lite`, the model of the frozen results: re-running those cases is answered from the cache |
| `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL` | no | Any OpenAI-compatible endpoint instead of Gemini |
| `MAX_DAILY_TOKENS` | yes | Live-model tokens per UTC day across all runs, e.g. `1000000` (a full 29 × 5 run uses about 0.55 M) |
| `MAX_CASES_PER_RUN` | no | Cases in one run (default 30) |
| `RATE_LIMIT_PER_MINUTE` | no | Requests per minute per client IP (default 240; health is exempt) |
| `AUTH_MAX_ATTEMPTS`, `AUTH_LOCKOUT_MINUTES` | no | Lockout after wrong access codes (defaults 5 and 15) |
| `SESSION_HOURS` | no | Session length after unlocking (default 12) |
| `STEP_DEADLINE_S` | no | Seconds one step may run before it is stored as "timeout" (default 240, below `maxDuration`) |
| `RUN_STALE_S` | no | A run with no progress for this long is marked interrupted (default 600) |
| `MAX_BODY_BYTES` | no | Request body limit (default 2,000,000; Vercel's own limit is 4.5 MB) |
| `TEMPERATURE`, `MAX_STEPS`, `MAX_OWNER_QUESTIONS` | no | Agent settings (defaults 0, 6, 5) |
| `PRICE_INPUT_PER_MTOK`, `PRICE_OUTPUT_PER_MTOK` | no | USD per million tokens, for cost figures |

Set them for **Production** (and Preview if you use preview deployments; give previews their own Neon branch,
which the Neon integration can create, so tests never touch production data).

## 5. Migrations and seed (from your computer)

The database is set up once from your computer, where the SVTG PDF is. Get the **direct** connection string:
the value of `DATABASE_URL_UNPOOLED` (Vercel → Settings → Environment Variables, or the connection details under
Storage → your database), or the Neon console → Connect with connection pooling turned off.

In PowerShell, from the repository root:

```powershell
# Point this terminal (only) at the production database. Never commit these values.
$env:DATABASE_URL_UNPOOLED = "postgresql://...neon.tech/neondb?sslmode=require"   # the direct URL
$env:DATABASE_URL = $env:DATABASE_URL_UNPOOLED
$env:APP_ENV = "production"                                    # the seed then also removes any demo runs
$env:SVTG_PDF_PATH = "C:\path\to\StandardVeterinaryTreatment.pdf"

cd backend
..\.venv\Scripts\alembic.exe upgrade head                     # create the tables (safe to repeat)
..\.venv\Scripts\python.exe -m app.scripts.seed                # data, frozen results, cache, SVTG passages
cd ..

Remove-Item Env:DATABASE_URL, Env:DATABASE_URL_UNPOOLED, Env:APP_ENV, Env:SVTG_PDF_PATH
```

Expected output of the seed (the first time):

```text
Database: postgresql
  benchmark data : loaded 29 cases and 31 drug rows
  results        : loaded run 20261019-090352-249aa9; 145 answer(s) added to the cache
  SVTG passages  : loaded 2022 passages from 406 pages (StandardVeterinaryTreatment.pdf)
Benchmark 1.0.0 (b4b15a693070), 29 cases, 31 drug rows; 1 run(s); 2022 SVTG passages.
```

Running it again changes nothing ("already loaded"). Cases or drug rows edited in the app are kept unless you
pass `--reset-data`. Without the PDF the seed skips the passages and says so; the site still starts, and
`/api/health` reports `"index_loaded": false` with a warning until you seed them.

On macOS or Linux the same steps are `export VAR=...`, `../.venv/bin/alembic upgrade head` and
`../.venv/bin/python -m app.scripts.seed`.

## 6. Function duration (maxDuration)

`vercel.json` gives the API service's function (`app/main.py` in `backend/`) `"maxDuration": 300`, the Hobby
plan's maximum. Runs are split so that one
request handles one case through one condition, and a step stops at `STEP_DEADLINE_S` (240 s) to leave time to
store a "timed out" result that you can retry. A condition usually takes seconds (C3 and C4 make several model
calls). On a Pro plan you can raise `maxDuration` to 800 in `vercel.json` and `STEP_DEADLINE_S` accordingly.

Then deploy: **Deployments → Redeploy** (or push to `main`).

## 7. Custom domain (optional)

Project → **Settings → Domains** → add your domain and create the DNS record Vercel shows. Then set
`ALLOWED_ORIGINS` to the new `https://` origin and redeploy. Session cookies are `Secure` and `SameSite=Strict`,
so the site must be opened over HTTPS on one domain.

## 8. Post-deploy smoke test

Replace `<url>` with your deployment, e.g. `https://vetagent.vercel.app`.

- [ ] `curl.exe -s <url>/api/health` shows `"version": "1.1.0"`, `"environment": "production"`,
      `"database": {"ok": true, "engine": "postgresql"}`, `"index_loaded": true`, `"chunks": 2022`,
      `"source_pages": 406`, `"benchmark": {"version": "1.0.0", "frozen": true, ...}`, `"counts": {"runs": 1, ...}`,
      `"warnings": []`, `"mode": "public"`.
- [ ] `curl.exe -sI <url>/` lists `content-security-policy` (with `frame-ancestors 'none'`),
      `x-content-type-options: nosniff`, `referrer-policy: no-referrer`, `strict-transport-security`.
- [ ] `curl.exe -s -X POST <url>/api/runs -H "Content-Type: application/json" -d "{\"case_ids\":[\"BOV-WD-007\"]}"`
      returns 401 "Read-only mode. Enter the access code ...".
- [ ] `<url>/StandardVeterinaryTreatment.pdf` returns the app's page, never a PDF.
- [ ] Overview shows "Benchmark v1.0.0 content hash b4b15a693070"; Scorecard shows the `gemini-3.5-flash-lite`
      run of 2026-10-19 with 145 results; Export CSV starts with the disclaimer.
- [ ] Unlock with the access code, open BOV-WD-007 and press **Run case**: C0 to C4 fill one after another (one
      request each). With `GEMINI_MODEL=gemini-3.5-flash-lite` they come from the cache and spend no tokens; the run
      bar shows today's budget.
- [ ] Lock again; Review and Settings ask for the code.
- [ ] Optional: the release suite against the deployment:

  ```powershell
  cd frontend
  $env:E2E_BASE_URL = "<url>"; $env:E2E_ACCESS_CODE = "<code>"
  npx playwright test -c playwright.release.config.ts release
  ```

When everything passes, add the URL to the README and the repository's About section:
`.\scripts\set-live-url.ps1 -Url <url>`.

## Test a production build locally

On Vercel the `api` service runs `app.main:app` from `backend/` and the CDN serves the frontend. Locally, the same
entrypoint also serves the built frontend, so one server stands in for both services:

```powershell
npm --prefix frontend run build
$env:APP_ENV = "production"; $env:COOKIE_SECURE = "false"            # plain http on localhost
$env:DATABASE_URL = "postgresql://..."                               # a test database, migrated and seeded
$env:ADMIN_ACCESS_CODE = "<code>"; $env:SESSION_SECRET = "<secret>"; $env:ALLOWED_ORIGINS = "http://localhost:8000"
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000   # from the repository root
```

Then `cd frontend; $env:E2E_BASE_URL = "http://localhost:8000"; $env:E2E_ACCESS_CODE = "<code>";
npx playwright test -c playwright.release.config.ts`. Run the server with `RATE_LIMIT_PER_MINUTE=3000` for the
browsing tests: they make hundreds of requests a minute. For the budget and rate-limit checks, start a second
server on another port with its own database, `MAX_DAILY_TOKENS=1000` and `RATE_LIMIT_PER_MINUTE=30`, and set
`E2E_BUDGET_URL` and `E2E_LIMIT_URL` to it.

With the [Vercel CLI](https://vercel.com/docs/cli) you can also run the project the way Vercel builds it:
`npx vercel login`, `npx vercel link`, then `npx vercel build` (checks `vercel.json`) or `npx vercel dev`.

## Limitations on Vercel

- **Time limit per request.** Each step (one case, one condition) must finish within `maxDuration` (300 s on
  Hobby). A step still working at `STEP_DEADLINE_S` is stored as "timed out" with a Retry button; nothing else
  is lost. A whole run is many requests, driven by the browser.
- **Keep the tab open during a run.** The browser asks for each step in turn. A reloaded page continues the run;
  a run left without progress for `RUN_STALE_S` (10 minutes) is marked interrupted.
- **One run at a time** across all visitors (a second run is refused until the first ends).
- **Cold starts.** The first request to a new function instance loads the SVTG passages from the database to build
  the search index (about 2,000 passages; typically a second or two).
- **Streaming.** Steps stream to the browser as server-sent events. If something between the browser and the
  function buffers the stream, the card still fills in when the step ends.
- **Read-only public mode.** Visitors cannot run or edit anything; live runs need the access code, and the
  daily token budget caps spending.
- Vercel's Hobby plan is meant for personal, non-commercial projects; check that this use fits its terms.

## Operations

- **Logs** (Vercel → Logs) contain method, path, status and timing; no request bodies, prompts, case text or
  keys. Anything shaped like an API key is redacted before it is written.
- **Budget.** `MAX_DAILY_TOKENS` counts live, uncached tokens per UTC day (table `budget_usage`). A run that
  crosses it stops after the step that crossed it, and new runs are refused with a clear message until 00:00 UTC.
- **Access code.** Compared as a salted scrypt hash in constant time. After `AUTH_MAX_ATTEMPTS` wrong codes
  from one IP (taken from Vercel's `X-Real-IP` header), that IP is locked out for `AUTH_LOCKOUT_MINUTES`; six
  times as many failures from all IPs together lock everyone out. Counters are in the database, so every
  function instance enforces them. Changing the code or `SESSION_SECRET` signs everyone out.
- **Backups.** Neon keeps a restore window (point-in-time restore, branches); see your Neon plan. The data is
  also reproducible: the seed files, the snapshot and the PDF rebuild everything except new runs and reviews,
  which you can export from the Runs and Scorecard pages (JSON / CSV).
- **Updating.** Push to `main`; Vercel builds and deploys. If a release adds a migration, run
  `alembic upgrade head` (step 5) before or right after the deploy. To take a new case set, run the seed with
  `--reset-data`. `/api/health` shows the benchmark hash; `"frozen": false` means the data no longer matches
  v1.0.0.
- **Frozen results.** `snapshots/v1.0.0/run.json` is the complete live run `20261019-090352-249aa9` with a
  SHA-256 in `run.sha256`. `python -m app.scripts.snapshot verify` re-scores it against the seed files.
