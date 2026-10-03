# Demo script — VetAgentBench-IN (about 10 minutes)

Research prototype — not for clinical use. Consult a registered veterinarian.

## Before the meeting (15 minutes)

1. **Choose live or demo.**
   - *Live (recommended):* create `.env` from `.env.example`, set `LLM_PROVIDER=gemini` and `GEMINI_API_KEY=…`
     (and optionally `PRICE_INPUT_PER_MTOK` / `PRICE_OUTPUT_PER_MTOK` from the provider's price page).
   - *Demo (no key):* leave the key empty and set `DEMO_DELAY_MS=250` so the streaming is visible. The banner
     "Demo mode: sample responses, not live model output" stays on every page. **Do not present demo numbers as results.**
2. Start the app: `npm run dev` (or `run.bat`) and open http://localhost:5173.
3. Settings → **Test connection** → expect "OK · Connected" (live) or "Demo mode" (demo).
4. Produce real numbers: Bench → **Run all (29)** — 145 condition runs. In live mode allow several minutes; the run
   bar shows progress and can be cancelled. Then open Scorecard to check it scored the new run.
5. Optional for Review: rate a handful of answers so the agreement panel is populated.

## The walk-through

| Time | Page | What to show | What to say |
|---|---|---|---|
| 0:00 | **Overview** | Status strip, the five conditions, headline numbers | The question: do retrieval, tools, self-verification and hard rules make advice safer? We measure dangerous errors first, accuracy second. |
| 1:00 | **Study Design** | The ablation ladder | Each condition adds exactly one component; same model, same answer schema, temperature 0. Owner-interview variant hides the case. |
| 2:00 | **Bench** → BOV-WD-007 | Signalment, owner narrative, question; press **G** to reveal gold (2-day milk withdrawal, SVTG p.175); press **G** again | A real Indian scenario: buparvaquone for theileriosis; when can the milk be sold? |
| 3:00 | **Bench** → press **Shift+R** | Steps streaming into C0–C4; the trace (tool calls with latency and tokens); stamps landing | C0 answers from memory; C1 cites SVTG pages; C2 looks up the drug table (dose maths in Python); C3 checks its claims; C4 applies rules. Click a citation chip → the SVTG passage. |
| 5:00 | **Bench** → BOV-009 (Ctrl+K, type BOV-009) | Ketoprofen question | The SVTG itself still lists a ketoprofen dose, but ketoprofen is banned for animal use in India. Watch whether each condition catches it; C4's `banned_drug` rule fires. |
| 6:00 | **Bench** → FEL-SAFE-004 | Paracetamol in a cat | Not in the SVTG (livestock only). Retrieval cannot help; the drug table and rules must. |
| 7:00 | **Scorecard** | Tiles, dot-and-whisker charts, McNemar table, breakdowns; **CSV** export | Every rate has a 95% Wilson interval; McNemar compares adjacent conditions on the same cases. With 29 cases intervals are wide — this is a pilot. |
| 8:30 | **Review** | Blind rating with **1 / 2 / N**; reveal condition and auto verdict; κ panel | The automatic scorer must be checked by a veterinarian: Cohen's κ between vet and scorer. |
| 9:30 | **Cases / Drug Table** | UNVERIFIED tags, an edit with validation (e.g. cattle weight 90 kg → rejected) | All gold answers and drug rows await veterinary sign-off; numbers only where a source states them. |

## Shortcuts worth showing

Ctrl+K command palette · **?** shortcut sheet · J/K move · R run · Shift+R force re-run · 1–5 jump to a condition ·
G gold · X select for batch run · Review: 1 / 2 / N.

## Honest caveats to state

- The SVTG has no dog or cat chapters; companion-animal cases are sourced from general veterinary toxicology.
- Withdrawal periods are rarely stated in the SVTG; three of four withdrawal cases test refusal to invent a number.
- Gold answers, triage and escalation labels are the author's judgments pending veterinary review.
- Ban notifications (diclofenac, ketoprofen, aceclofenac) are recorded by year; gazette numbers still need verifying.
- 29 cases: treat p-values as exploratory.

## If something goes wrong

- **Top bar says "Backend offline":** the API is not running on 127.0.0.1:8010 — restart `npm run dev`.
- **A condition card shows an error:** the real provider error is printed on the card (quota, invalid key, …).
  Fix it in `.env`/Settings and press Shift+R.
- **Port 8000 is busy:** irrelevant — this project uses 8010.
- **Live provider fails during the meeting:** remove the key (or set the provider to Demo in Settings) and say so;
  the app keeps working with clearly labelled sample responses.

## Screenshots

`docs/screenshots/<page>-<1440|1024>-<light|dark>.png` — Bench, Runs, Review, Cases, Drug Table, Scorecard,
Study Design, Overview, Settings. Milestone evidence screenshots are the `m1-` … `m7-` files.
