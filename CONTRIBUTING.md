# Contributing to VetAgentBench-IN

Thank you for helping. This is a research prototype, not for clinical use, and contributions are judged first on
whether they keep the benchmark honest and reproducible.

## Ground rules

- **No invented clinical numbers.** Doses, withdrawal periods and ban references need a cited source (document and
  page). If no source states a number, leave the field empty and mark the row unverified.
- **New cases and drug rows start unverified** (`vet_verified: false`, empty `verified_by`).
- **The benchmark is frozen at v1.0.0.** Any change to `data/cases.json` or `data/drug_table.csv` changes the
  content hash and makes the benchmark `1.0.0+modified`. Data changes go in their own pull request and need a new
  benchmark version (`python -m app.scripts.benchmark`).
- **Never commit secrets.** `.env` is gitignored; health and logs show only whether a key is present.
- **The SVTG PDF is never committed or served.** Download it from DAHD (see the README).

## Setup

See [Getting started](README.md#getting-started) in the README. In short:

```bash
npm run setup                 # Windows; on macOS/Linux see the README
cp .env.example .env          # optional: add a model key; without one the app runs in demo mode
npm run dev                   # first start creates and seeds the local SQLite database
```

The app reads everything from a database: SQLite (`data/vetagentbench.db`) unless `DATABASE_URL` points at
Postgres. A schema change needs an Alembic migration in `backend/migrations/versions/`
(`cd backend; python -m alembic revision --autogenerate -m "..."`, then review it); `test_seed.py` fails if the
migrations and `app/storage/schema.py` disagree. Runtime Python packages go in `requirements.txt` (what Vercel
installs); tools that never run on the server go in `backend/requirements-dev.txt`.

## Commit message hygiene

The repository ships a `commit-msg` hook that keeps commit messages free of tool-attribution lines. It removes
`Co-Authored-By:` trailers, `Generated with ...` lines and `<Tool>-Session:` trailers, then trims trailing blank
lines. Install it once per clone:

```bash
sh scripts/install-hooks.sh          # macOS / Linux / Git Bash
```

```powershell
.\scripts\install-hooks.ps1          # Windows PowerShell
```

Both set `git config core.hooksPath .githooks`. To check that it is active: `git config core.hooksPath`.

Write commit messages in the imperative ("Add goat withdrawal case"), with a short first line and a body that
explains why.

## Before you open a pull request

```bash
npm test                                   # backend pytest (SQLite; TEST_DATABASE_URL=postgresql://... for Postgres)
npm --prefix frontend run check            # tsc, eslint, style, contrast and motion checks
npm --prefix frontend run build            # production build
npm --prefix frontend run check:secrets    # no secret in the built frontend
cd backend && python -m app.scripts.snapshot verify   # the frozen results still reproduce
```

CI runs the same checks on every push and pull request. For interface changes, attach screenshots at 1440 and
1024 px. The design rules (colours, type, motion) are in [docs/DESIGN.md](docs/DESIGN.md) and
[docs/MOTION.md](docs/MOTION.md); `check:style`, `check:contrast` and `check:motion` enforce most of them.

## Reporting problems

- Bugs and ideas: [open an issue](https://github.com/Shubhomoy919/VetAgent/issues/new/choose).
- Security problems: report them privately, see [SECURITY.md](SECURITY.md).

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE).
