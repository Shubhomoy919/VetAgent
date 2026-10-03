# VetAgentBench-IN

A research prototype that tests whether LLM agents give safer veterinary advice than a bare LLM,
using India's Standard Veterinary Treatment Guidelines (SVTG) as the knowledge source.

**Research prototype — not for clinical use. Consult a registered veterinarian.**

## Setup (Windows)

Requires Python 3.11+ and Node 20+.

```powershell
npm run setup          # creates .venv, installs Python and npm dependencies
copy .env.example .env # optional: add an API key; without one the app runs in demo mode
```

## Run

```powershell
npm run dev            # or: run.bat
```

`npm run dev` does not auto-reload the backend: on Windows, uvicorn's reloader sends CTRL+C to the whole console
and takes the frontend down with it. When working on backend code, run `npm run dev:api:watch` and
`npm run dev:web` in two terminals instead. For demos without an API key, set `DEMO_DELAY_MS=250` in `.env` so
streamed steps are visible.

- Frontend: http://localhost:5173 (proxies `/api` to the backend)
- Backend: http://127.0.0.1:8010 — health at `/api/health`
  (8010 rather than 8000, because other local projects occupy 8000 on the dev machine)

## Run cases from the command line

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.scripts.run_case BOV-WD-007                 # all five conditions
..\.venv\Scripts\python.exe -m app.scripts.run_case BOV-009 --conditions C0,C4 --force
..\.venv\Scripts\python.exe -m app.scripts.run_case CAN-013 --interview        # owner-interview mode (C0, C3)
```

Score a run (latest multi-case run by default) and write the CSV to `data/exports/`:

```powershell
..\.venv\Scripts\python.exe -m app.scripts.score
..\.venv\Scripts\python.exe -m app.scripts.score <run_id> --csv ..\data\exports\my.csv --json ..\data\exports\my.json
```

Results are stored in `data/runs.db`. Without an API key the demo provider answers: sample responses built from
the case text and tool results (never the gold answer), labelled `[Demo]`, not live model output.

## Settings

The Settings page edits non-secret settings (provider, models, temperature, max steps, prices, PDF path). Changes
are saved to `data/settings.json` (gitignored) and override `.env`; "Reset to .env" removes them. API keys are
never shown or stored there — put them in `.env`.

## Checks

```powershell
npm test               # backend pytest
npm run typecheck      # frontend tsc
npm run lint           # frontend eslint
npm --prefix frontend run e2e   # Playwright
```

See `CLAUDE.md` for the full spec and `docs/DESIGN.md` for the design system.
