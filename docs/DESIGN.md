# Design — black and pink

One look: **Riso Black**. A pure black ground with paper and ink accents, in the manner of a risograph
field notebook. **Pink `#FF4F9A` is the single UI accent.** Every other ink appears only where it encodes
data: the condition colours C0–C4, safe/unsafe states, and species tags. Anything that did not serve the
research has been removed.

| Where | What |
|---|---|
| `frontend/scripts/gen_tokens.py` | Source of truth for colour; writes `src/styles/tokens.css` (`npm run tokens`). |
| `frontend/scripts/tokens.static.css` | Non-colour tokens (type, space, shape, motion, `@property`). |
| `frontend/scripts/check-contrast.ts` | WCAG check of every text/background pair the UI uses (`npm run check:contrast`). |
| `frontend/scripts/check-style.mjs` | Banned-style and stray-colour check (`npm run check:style`). |
| `frontend/scripts/find-dead-css.mjs` | Dev helper: lists CSS classes no component uses. |
| `frontend/src/styles/` | `tokens`, `grounds` (grid, grain, ink-bleed), `patterns` (tag hole mask), `effects`, `controls`, `ledger`, `layout`, `motion`, `print`, `themes` (chrome token scoping, hero). |

## Colour

Components use only semantic tokens; colour literals live only in `tokens.css` (enforced by `check:style`).

| Role | Token | Value |
|---|---|---|
| Ground (pure black) | `--bg`, `--sidebar`, `--surface`, `--raised` | `#000000` |
| Hairlines | `--rule` / `--rule-soft` | `#2A2A2A` / `rgba(244,239,230,.13)` |
| Grid | `--grid-minor` / `--grid-major` | `rgba(255,255,255,.035)` / `rgba(255,255,255,.06)` |
| Text | `--text`, `--text-body`, `--text-muted`, `--text-dim` | `#F4EFE6`, `#E4DFD6`, `#B8B2A8`, `#8A847A` |
| Text on an ink fill | `--text-on-ink` | `#10201F` (never white) |
| Paper | `--paper`, `--paper-text`, `--paper-muted` | `#F5EBDD`, `#10201F`, `#4B5655` |
| **Accent (UI)** | `--ink-pink` → `--accent`, `--info`, `--running`, `--caution`, `--focus-ring`, `--nav-active-bg`, `--sheet-shadow`, `--selection` (35%) | `#FF4F9A` |
| Conditions (data) | `--c0 … --c4` (+ `-text`, `-paper`) | orange `#FF7A2F`, cornflower `#5B8CFF`, violet `#9B7BFF`, mint `#6EE7C8`, sunflower `#FFC933` |
| Safe / unsafe (data) | `--safe` / `--unsafe` (+ `-text`, `-paper`) | mint `#6EE7C8` / madder `#E5484D` |
| Species tags (data) | `--sp-can/fel/bov/cap/avi` | orange / violet / cornflower / mint / sunflower |

Rules: black dominates; inks never become page backgrounds. Text on an ink fill is `--text-on-ink`. Madder
is never a background for small text: danger states use `--unsafe-tint` (madder mixed into the ground) with
normal text. Tints are `color-mix()` only. Paper marks that failed 3:1 on paper were deepened in OKLCH
lightness: paper-orange `#E8601C → #E15910`, paper-mint `#1FAE8C → #009574`, paper-sunflower
`#D99A00 → #B57800`.

**Contrast:** `check-contrast.ts` checks 105 pairs (all text tokens on every panel, paper and hero text,
text-on-ink on every fill, chrome, focus ring, chart marks) — all pass; the lowest text ratio is 5.00:1.

## Type
Instrument Serif for display and big numbers (40 / 56 / 72); IBM Plex Sans for the UI; IBM Plex Mono for IDs,
data and traces. Small caps for section labels; tabular numerals everywhere; `text-wrap: balance` on headings;
hanging punctuation in running text. Self-hosted via `@fontsource`.

## Ground (`grounds.css`)
Pure black base, an 8/40px graph grid, paper grain (SVG noise), and **one pink ink-bleed cloud** per page at
the top-right, screen-blended and masked so it never sits behind text. No other ground decoration.

## Components that remain
| Component | Purpose |
|---|---|
| Logo (`InkMark`) | Three overlapping pink dots at 100 / 60 / 32% plus the pink wordmark. |
| Active nav marker | Pink bar that slides to the active item. |
| `SpecimenPlate` | Case header: species code, Latin binomial, breed, signalment strip, lab-log line ("examined N times · last run HH:MM"). |
| `SpecimenTag` | Luggage-tag case ID with a species stripe and punched hole (mask in `patterns.css`). |
| `VitalTrace` | ECG-style line per condition card: beats for model steps, labelled spikes for tools, a flat madder segment for errors; spikes open the trace log. |
| `DoseDial` | Safe band from the drug table (mg/kg × weight, computed in Python) and the model's dose; DO NOT GIVE for banned / contraindicated; NO DATA — UNVERIFIED when the table has no range. |
| `TriageStrip` | ROUTINE / URGENT / EMERGENCY with an under-triage notch at the gold level. |
| `Stamp` | Verdict stamps (roughened ink edges): CORRECT, FALSE-SAFE, ILLEGAL DRUG, UNDER-TRIAGE, MISSED ESCALATION, WITHDRAWAL ERROR, ESCALATED, DO NOT GIVE. |
| `Switchboard` | Retrieval / Tools / Verify / Guardrail toggles; used in the Scorecard legend, Overview and Study Design. |
| `Sidenotes` | Citations as superscripts; margin notes on wide cards, popovers on narrow ones. |
| Ledger tables | Small-caps sticky headers, madder margin rule, aligned numerals. |
| Segmented meter + LEDs | Run progress (one segment per result) and per-condition status. |
| Key caps (`kbd`) | Physical keys that press when their shortcut fires. |
| `EmptySpecimen` | Empty and 404 plates ("No specimen examined yet", "Specimen not found"). |

Depth: hairlines only. The Scorecard hero is a paper ticket; no other element carries a shadow.

## What was removed (and why)
The two alternate themes, theme switching and its transition (one look); the keyboard launcher and its
top-bar button; the first-run coach marks; density and ledger-density toggles; the Settings palette page;
the printer's colour strip and the corner marks; per-card switchboards (repeated the legend); plate Roman numerals,
run-bar screws and the meter percentage (decoration / duplicates); chart crosshair (the tooltip gives exact
values); top-bar token / latency / cost readouts (totals are in Settings and the Scorecard); the Overview
Print button (the print report is on the Scorecard); Settings fields for owner questions, demo delay and
prices (still settable in `.env`).

## Settings
Provider; model (the field for the chosen provider; base URL only for OpenAI-compatible); temperature; max
tool steps; SVTG PDF status (read-only); Test connection; token and cost totals.

## Keyboard
`?` shortcut help · Bench: J/K, X, R, Shift+R, 1–5, G · Review: 1, 2, N, J/K. Never while typing.

## Banned
Glassmorphism, `backdrop-filter`, `blur(`; decorative gradients and gradient text; neon glows, blurred
shadows; emoji, sparkle or "AI" icons; generic logo squares; centred hero sections; bubbly cards; default
Tailwind/shadcn/chart styling; the Inter font; marketing copy; looping attention-seekers, parallax, blobs.
Gradient functions only for technical patterns in `patterns.css` and `grounds.css`. `npm run check:style`
enforces this, plus: colour literals only in `tokens.css`, no blurred box-shadows, `infinite` only for the
running LED.
