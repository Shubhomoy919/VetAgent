# Deploying VetAgentBench-IN v1.0.0

One container serves the API and the built frontend. It runs as a non-root user, keeps all writable state on one
persistent volume (`/data`), and on first start loads the frozen v1.0.0 results snapshot, so the public site
shows real numbers without spending API credits.

Research prototype, not for clinical use. Consult a registered veterinarian.

## What the public sees, and what needs the access code

| Anyone (read-only) | Needs `ADMIN_ACCESS_CODE` |
|---|---|
| Overview, Scorecard, Cases, Drug table, Runs, Study design | Running cases (Bench run bar, `R`) |
| The Bench with the stored results of a completed run | Editing or importing cases and drug rows |
| Cited SVTG passages, with page numbers and a link to DAHD's copy | Review (veterinarian ratings) |
| CSV / JSON exports (with disclaimer, benchmark hash, model, prompt, temperature) | Settings, Test connection, SVTG search |

The SVTG PDF is never served. Visitors get only passages that a stored answer or gold answer cites.

## 1. Before you start

- A host that runs a Docker image with a **persistent disk/volume**: Render (Web Service + Disk), Railway
  (service + Volume) or Fly.io (Machine + Volume). 512 MB RAM is enough; 1 GB is comfortable while indexing.
- The SVTG PDF: either upload it to the volume, or let the container download DAHD's copy on first start
  (`SVTG_PDF_URL`, set in `.env.production.example`).
- Two random secrets:

  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(24))"   # ADMIN_ACCESS_CODE
  python -c "import secrets; print(secrets.token_urlsafe(48))"   # SESSION_SECRET
  ```

## 2. Environment variables

Every variable is listed with comments in [`.env.production.example`](../.env.production.example). The ones you
must set:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` (the image already sets it) |
| `ALLOWED_ORIGINS` | your site's origin, e.g. `https://vetagentbench.example.org` |
| `ADMIN_ACCESS_CODE` | the access code (leave empty for a permanently read-only site) |
| `SESSION_SECRET` | 32+ random characters |
| `GEMINI_API_KEY` | only if you want live runs; without it runs are disabled and only stored results show |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` (the model of the v1.0.0 snapshot) |
| `MAX_DAILY_TOKENS` | daily live-token cap, e.g. `1000000` (a full 29 × 5 run uses about 0.55 M) |
| `SVTG_PDF_URL` | `https://dahd.gov.in/sites/default/files/2024-10/StandardVeterinaryTreatment.pdf` (or upload the file) |

Keep `DATA_DIR=/data` and mount the volume there. `PORT` is read from the environment (Render and Railway set
it; Fly uses `internal_port`).

## 3. Deploy

### Render

1. New → **Web Service** → connect the repository → Runtime **Docker** (it finds the `Dockerfile`).
2. **Disks** → Add disk: mount path `/data`, 1 GB.
3. **Environment** → add the variables above.
4. **Health check path**: `/api/health`.
5. Deploy. Then **Settings → Custom domain** → add your domain and create the DNS record Render shows.
   Set `ALLOWED_ORIGINS` to that `https://` origin and redeploy.

### Railway

1. New project → **Deploy from GitHub repo** (Railway builds the `Dockerfile`).
2. Service → **Volumes** → New volume, mount path `/data`.
3. **Variables** → add the variables above.
4. **Settings → Networking** → Generate domain or add a custom domain; set `ALLOWED_ORIGINS` to match.
5. **Settings → Deploy** → Healthcheck path `/api/health`.

### Fly.io

```bash
fly launch --no-deploy            # accept the Dockerfile; pick a region near your users (e.g. bom)
fly volumes create vab_data --size 1
fly secrets set ADMIN_ACCESS_CODE=... SESSION_SECRET=... GEMINI_API_KEY=... \
  ALLOWED_ORIGINS=https://<app>.fly.dev \
  SVTG_PDF_URL=https://dahd.gov.in/sites/default/files/2024-10/StandardVeterinaryTreatment.pdf
```

Add to the generated `fly.toml`:

```toml
[env]
  GEMINI_MODEL = "gemini-3.5-flash-lite"
  MAX_DAILY_TOKENS = "1000000"

[[mounts]]
  source = "vab_data"
  destination = "/data"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "stop"
  min_machines_running = 0

[[http_service.checks]]
  path = "/api/health"
  interval = "30s"
  timeout = "5s"
```

Run exactly **one** machine (`fly scale count 1`). See "Scaling" below. Then `fly deploy`, and for a custom
domain `fly certs add your.domain`.

## 4. Check the deployment

```bash
curl -s https://your.domain/api/health
```

Expect `"environment": "production"`, `"version": "1.0.0"`, `"benchmark": {"version": "1.0.0", "frozen": true, ...}`,
`"database": {"ok": true}`, `"pdf_loaded": true`, `"mode": "public"`, `"counts": {"runs": 1, ...}`.

```bash
curl -sI https://your.domain/ | grep -iE "content-security|x-content-type|referrer-policy|x-frame|strict-transport"
curl -s -X POST https://your.domain/api/runs -H 'Content-Type: application/json' -d '{"case_ids":["BOV-WD-007"]}'
# → 401 {"detail":"Read-only mode. Enter the access code ..."}
```

Open the site, check Overview shows "Benchmark v1.0.0" with the hash, and that the Scorecard shows the
`gemini-3.5-flash-lite` run of 2026-10-19 with all 145 results.

## 5. The frozen results snapshot

`snapshots/v1.0.0/run.json` is the complete live run `20261019-090352-249aa9` (29 cases × 5 conditions,
`gemini-3.5-flash-lite`, prompt v2, temperature 0, benchmark v1.0.0), with a SHA-256 in `run.sha256`.

- **Automatic:** with `AUTOLOAD_SNAPSHOT=true` (default) the server loads it into the database at startup if it
  is not there yet. Loading is idempotent.
- **By hand** (e.g. after wiping the database):

  ```bash
  docker compose exec vetagentbench python -m app.scripts.snapshot load      # Fly: fly ssh console -C "..."
  docker compose exec vetagentbench python -m app.scripts.snapshot verify    # re-score; must print OK
  ```

- **Demo data:** in production, demo runs are never created, never shown or exported, and any found in the
  database are deleted at startup. To clean a database by hand: `python -m app.scripts.snapshot purge-demo`.

## 6. Local test with docker compose

```bash
cp .env.production.example .env.production      # fill in ADMIN_ACCESS_CODE, SESSION_SECRET, (GEMINI_API_KEY)
# set ALLOWED_ORIGINS=http://localhost:8000 in .env.production for local testing
docker compose up --build -d
docker compose ps                                # STATUS shows (healthy) after ~40 s
open http://localhost:8000
```

The compose file mounts `./data/StandardVeterinaryTreatment.pdf` read-only and keeps the database on the
named volume `vab-data`, so `docker compose down && docker compose up -d` keeps every run.

Release e2e tests against the container. The browsing specs make hundreds of requests a minute, so run the
container under test with a high limit, and a second container with a tiny budget and a low limit for the
budget-cap and rate-limit checks:

```bash
RATE_LIMIT_PER_MINUTE=3000 docker compose up -d                       # (add it to .env.production for the test)
docker run -d --name vab-limits -p 8001:8000 --env-file .env.production   -e MAX_DAILY_TOKENS=1000 -e RATE_LIMIT_PER_MINUTE=30 -e ALLOWED_ORIGINS=http://localhost:8001   -v vetagentbench_vab-data:/data vetagentbench:1.0.0                 # shares the data volume (today's token use)
cd frontend
E2E_BASE_URL=http://localhost:8000 E2E_BUDGET_URL=http://localhost:8001 E2E_LIMIT_URL=http://localhost:8001   E2E_ACCESS_CODE=<code> npx playwright test -c playwright.release.config.ts
```

The live-run test spends about 25 k tokens when the answers are not cached yet. Put the production limits back
afterwards.

## 7. Backups

The database and editable data live on the volume. Back them up with SQLite's online backup (safe while running):

```bash
docker compose exec vetagentbench python -m app.scripts.backup --keep 14   # → /data/backups/<UTC timestamp>/
```

Schedule it with the host's cron (Render Cron Job, Railway cron, or `fly machine run ... --schedule daily`) and
copy `/data/backups` off the volume regularly. To restore, stop the service, copy a backup's `runs.db`,
`cases.json` and `drug_table.csv` into `/data`, and start it again.

## 8. Operations

- **Logs** contain method, path, status and timing only. No query strings, request bodies, prompts, case text or
  keys. Anything shaped like an API key is redacted before it is written.
- **Graceful shutdown:** on SIGTERM gunicorn stops accepting requests, the app cancels any active run and records
  its status (`cancelled`), and the worker exits within `GRACEFUL_TIMEOUT` (25 s). A run cut off by a crash is
  marked `interrupted` on the next start.
- **Compression:** static assets are pre-compressed at build time (Brotli and gzip) and served with
  `Content-Encoding`; API responses are gzipped; the SSE event stream is never compressed or buffered.
- **Budget:** `MAX_DAILY_TOKENS` counts live, uncached tokens per UTC day. A run that crosses it stops after the
  answer that crossed it (overshoot at most one answer), and new runs are refused with a clear message until
  00:00 UTC. `MAX_CASES_PER_RUN` caps one run; `RATE_LIMIT_PER_MINUTE` limits every endpoint per client IP
  (health is exempt).
- **Access code:** compared as a salted scrypt hash in constant time. After `AUTH_MAX_ATTEMPTS` wrong codes from
  one IP, that IP is locked out for `AUTH_LOCKOUT_MINUTES`. Six times as many failures from all IPs together lock
  everyone out for the same period. Sessions are signed (HMAC-SHA256) httpOnly, Secure, SameSite=Strict cookies
  for `SESSION_HOURS`. Changing the code or `SESSION_SECRET` signs everyone out.

## 9. Scaling, and switching to Postgres

The app runs **one worker process on purpose**. The active run, its live SSE event log, the rate-limit windows
and the lockout counters live in that process's memory, and SQLite allows one writer. For a research site this
handles hundreds of concurrent readers. To run several workers or machines:

1. Move run state and events to Redis (or Postgres `LISTEN/NOTIFY`), and rate-limit and lockout counters to Redis.
2. Move storage to Postgres. All SQL lives in `backend/app/storage/db.py`. The schema is portable except:
   `INTEGER PRIMARY KEY AUTOINCREMENT` becomes `BIGSERIAL PRIMARY KEY`; `json_each(...)` in `cited_pages()`
   becomes `jsonb_array_elements(answer::jsonb -> 'citations')`; `?` placeholders become `%s` (psycopg); and
   `PRAGMA` calls go. Replace `sqlite3.connect` in `Store._conn` with a psycopg connection pool from
   `DATABASE_URL`.
3. Copy data across with `python -m app.scripts.snapshot export <run_id>` + `load`, or a one-off SQL dump.

## 10. Updating

Build and deploy the new image; the volume is kept. Data files on the volume are never overwritten by a new
image. To take the new image's case set, delete `/data/cases.json` and `/data/drug_table.csv` before the
restart (back them up first). The Overview and `/api/health` show the benchmark hash, and `frozen: false` means
the live data no longer matches v1.0.0.
