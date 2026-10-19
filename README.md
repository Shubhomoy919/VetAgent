# VetAgentBench-IN

**Does giving a language model retrieval, tools, self-verification and hard safety rules make its veterinary
advice safer?** VetAgentBench-IN runs the same 29 India-focused, livestock-heavy cases through five conditions,
each adding one component to a bare model, and counts dangerous errors first and accuracy second. The knowledge
source is India's *Standard Veterinary Treatment Guidelines* (SVTG, DAHD 2024), and Indian drug bans are part of
the gold answers.

> **Research prototype, not for clinical use. Consult a registered veterinarian.**
> No case or drug row has been verified by a veterinarian yet. Every one carries an UNVERIFIED tag.

Version **1.0.0** · benchmark v1.0.0, content hash `b4b15a6930708f0976cb2b119f389c6d32ac321f8e2715d1751fed7c721edf07`

| Condition | Adds |
|---|---|
| C0 Bare LLM | nothing: the model answers from its own knowledge |
| C1 Retrieval | exactly one SVTG search; answers cite PDF pages |
| C2 Tools | a ReAct loop (≤ 6 steps): guideline search, drug safety with dose maths in Python, withdrawal lookup, patient record |
| C3 Self-verify | C2, then each claim is checked against retrieved evidence and revised |
| C4 Guardrail | C3, then deterministic rules: banned/contraindicated drug → "do not give", red flag → escalate, notifiable/zoonotic → report/warn |

## Results (frozen snapshot, v1.0.0)

One complete live run: `gemini-3.5-flash-lite`, prompt v2, temperature 0, 29 cases × 5 conditions, 145 of 145
answers schema-valid (run `20261019-090352-249aa9`, `snapshots/v1.0.0/run.json`).

| Metric | C0 | C1 | C2 | C3 | C4 |
|---|---|---|---|---|---|
| Top-1 diagnosis | 83% (24/29) | 83% | 90% (26/29) | 83% | 90% (26/29) |
| Any dangerous error ↓ | 7% (2/29) | 7% | 3% (1/29) | 7% | 3% (1/29) |
| False-safe drug ↓ | 17% (1/6) | 17% | 0% (0/6) | 0% | 0% |
| Illegal drug ↓ | 50% (1/2) | 50% | 0% (0/2) | 0% | 0% |
| Withdrawal error ↓ | 25% (1/4) | 0% | 0% | 0% | 0% |
| Missed escalation ↓ | 0% (0/20) | 0% | 0% | 5% (1/20) | 0% |

With 29 cases the 95% Wilson intervals are wide and the McNemar tests are exploratory; the Scorecard shows both.
This is a pilot, not evidence of clinical safety.

## Screenshots

| | |
|---|---|
| ![Bench, read-only, with a completed run](docs/screenshots/release/bench-public-1440.png) | ![Scorecard with provenance](docs/screenshots/release/scorecard-public-1440.png) |
| ![Overview](docs/screenshots/release/overview-public-1440.png) | ![Drug table with UNVERIFIED tags](docs/screenshots/release/drugs-public-1440.png) |

Every page at 1440, 1024 and 768 px, in every state, is in [`docs/screenshots/release/`](docs/screenshots/release/).

## Run locally (development)

Requires Python 3.11+ and Node 20+. Windows commands shown; on macOS/Linux use `.venv/bin/python`.

```powershell
npm run setup              # .venv + Python deps (incl. pytest) + npm deps
copy .env.example .env     # optional: add GEMINI_API_KEY; without a key the app runs in demo mode
npm run dev                # or run.bat → http://localhost:5173 (API on 127.0.0.1:8010)
```

The SVTG PDF is not in the repository. Download DAHD's copy to `data/StandardVeterinaryTreatment.pdf`:
<https://dahd.gov.in/sites/default/files/2024-10/StandardVeterinaryTreatment.pdf>.

In development with no `ADMIN_ACCESS_CODE` everything is unlocked. Demo mode answers are labelled
"Demo mode: sample responses, not live model output" and are never shown in production.

Command line:

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.scripts.run_case BOV-WD-007         # all five conditions for one case
..\.venv\Scripts\python.exe -m app.scripts.score                        # score the latest run → data/exports/
..\.venv\Scripts\python.exe -m app.scripts.snapshot verify              # re-score the frozen snapshot
..\.venv\Scripts\python.exe -m app.scripts.benchmark --check            # data still matches benchmark v1.0.0?
```

Checks:

```powershell
npm test                                   # backend pytest
npm --prefix frontend run check            # tsc, eslint, style, contrast, motion
npm --prefix frontend run e2e              # Playwright against the dev server
```

## Deploy

One Docker container (API + built frontend, gunicorn, non-root, health check) with a persistent volume. Public
visitors get a read-only site; runs, editing, Review and Settings need an access code. API spend is capped per
day. Step-by-step instructions for Render, Railway and Fly.io, every environment variable, backups and the
frozen snapshot are in **[docs/DEPLOY.md](docs/DEPLOY.md)**.

```bash
cp .env.production.example .env.production   # fill in the secrets
docker compose up --build                    # → http://localhost:8000
```

## Documentation

- [docs/DEPLOY.md](docs/DEPLOY.md): deployment, security model, operations
- [docs/DATA_CARD.md](docs/DATA_CARD.md): cases, drug table, SVTG ingestion, provenance, known gaps
- [docs/DEMO.md](docs/DEMO.md): the 10-minute meeting walkthrough
- [docs/DESIGN.md](docs/DESIGN.md), [docs/MOTION.md](docs/MOTION.md): design system and motion inventory
- [CHANGELOG.md](CHANGELOG.md)

## Limitations

- **Unverified gold standard.** Gold answers, triage levels and escalation labels are the author's judgement from
  the SVTG text. No veterinarian has reviewed them yet.
- **Small sample.** 29 cases and one model; intervals are wide, and differences between conditions are not
  statistically established.
- **Coverage.** The SVTG covers livestock and poultry only. The six dog and cat cases come from general
  veterinary toxicology, not the SVTG.
- **Withdrawal periods** are rarely stated in the SVTG, so three of the four withdrawal cases test whether a model
  refuses to invent a number.
- **Automatic scoring** uses synonym lists and rules. The Review page measures its agreement with a veterinarian
  (Cohen's κ), but no review has been done for v1.0.0.
- **Ban references.** Diclofenac, ketoprofen and aceclofenac bans are recorded by year; gazette numbers are not
  verified.
- **Single model snapshot.** The frozen results come from one provider and model at temperature 0. Other models,
  and later versions of this one, will differ.

## How to cite

See [CITATION.cff](CITATION.cff) (GitHub shows a "Cite this repository" button).

> Sarkar, S. (2026). *VetAgentBench-IN: do LLM agents give safer veterinary advice than a bare LLM?* (Version 1.0.0)
> [Computer software]. Benchmark v1.0.0, content hash b4b15a693070.

## Licence

Code: [MIT](LICENSE). The SVTG is a publication of the Department of Animal Husbandry and Dairying, Government of
India, and is not redistributed here. Get it from DAHD.

**Research prototype, not for clinical use. Consult a registered veterinarian.**
