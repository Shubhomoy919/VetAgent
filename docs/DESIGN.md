# Specimen v2 — "Ink & Pigment"

A field-lab notebook printed on a risograph: warm paper, deep pigment inks, crisp hairlines, ink stamps,
halftone shading and slight print misregistration. Colour is bold but disciplined — large calm areas, and small,
intense pigment accents exactly where attention matters: running state, verdicts, selection, key numbers.

This file is the reference. Every page and every future milestone uses it.

| Where | What |
|---|---|
| `frontend/scripts/gen_tokens.py` | **Source of truth for colour.** Generates `src/styles/tokens.css` (`npm run tokens`). |
| `frontend/scripts/tokens.static.css` | Non-colour tokens (type, space, shape, motion, density, `@property`), appended by the generator. |
| `frontend/src/styles/tokens.css` | Generated tokens: hex values, then an `@supports (color: oklch(…))` layer with the same colours in OKLCH. |
| `frontend/src/styles/patterns.css` | The **only** file allowed gradient functions — technical patterns only (halftone, grid, punched hole, perforation, meter scale). |
| `frontend/src/styles/effects.css` | The effects library (numbered 1–10 below) plus crop marks, tick-boxes, inputs, row markers. |
| `frontend/src/styles/motion.css` | View Transitions, scroll-driven reveals, § section heads. |
| `frontend/src/styles/controls.css` | Mechanical buttons and toggles. |
| `frontend/src/styles/print.css` | Print: plain paper; the Scorecard as a one-page A4 lab report. |
| `frontend/scripts/check-contrast.mjs` | WCAG check of every text token in both themes (`npm run check:contrast`). |
| `frontend/scripts/check-style.mjs` | Banned-style check (`npm run check:style`). |

## Colour

No ad-hoc colours anywhere: colour literals exist only in `tokens.css` (enforced by `check:style`). Tints are
derived with `color-mix()`. **Pigments** are for fills, marks and borders; each pigment has a **`-text` twin** — the
same hue, shifted only in OKLCH lightness until it reaches 4.6:1 on every background of the theme — used whenever the
colour is text. `[data-cond="Cn"]` sets `--cond` and `--cond-text` globally.

### Light — "Bone & Pigment"
| Token | Hex | Text twin | Use |
|---|---|---|---|
| `--bg` bone | `#F2EDE3` | | app background |
| `--surface` paper | `#FBF8F2` | | panes, sidebar, cards |
| `--raised` | `#FFFFFF` | | buttons, tags, hero, slips |
| `--ink` | `#121418` | | primary text |
| `--ink-2` graphite | `#575C66` | | secondary text, labels |
| `--rule` | `#D9D1C1` | | 1px hairlines |
| `--indigo` (neel) | `#1E2A78` | same | primary, ESCALATED, BOV stripe |
| `--peacock` | `#00727A` | `#006F77` | secondary, misregistration (right), FEL stripe |
| `--marigold` | `#F2A007` | `#9C5000` | running, meter, diffs, `::selection` (35%), AVI stripe |
| `--riso` (riso-pink) | `#E8447C` | `#C0135C` | signature pop: focus ring, active-nav marker, case selection edge, underlines, misregistration (left), coach marks — ≈ 2% of a screen |
| `--vermilion` | `#D23B1F` | `#C02706` | unsafe: FALSE-SAFE / UNDER-TRIAGE stamps, errors |
| `--leaf` | `#2E7D32` | `#247429` | safe: CORRECT, live, done LEDs, CAP stripe |
| `--terracotta` | `#B4532A` | `#A7471C` | caution, CAN stripe |

Derived: `--surface-sunk` = ink 4% into bone; `--rule-strong` = ink 14% into rule; `--scrim` = ink 22%;
`--selection` = marigold 35%; `--grid-minor/major` from rule; `--meter-face` = ink (light) / bg (dark).
`--focus` = `--riso-text` (riso itself is 2.99:1 on the sunk well, just under the 3:1 needed for a focus ring).
`--on-marigold` = ink (light) / bg (dark). Print uses `--print-paper` / `--print-ink`.

### Dark — "Night Lab"
| Token | Hex | Text twin |
|---|---|---|
| `--bg` | `#0D0F14` | |
| `--surface` | `#151922` | |
| `--raised` | `#1C2130` | |
| `--ink` | `#ECE7DD` | |
| `--ink-2` | `#9BA3AE` | |
| `--rule` | `#262C38` | |
| `--indigo` | `#8C9BFF` | same |
| `--peacock` | `#3CC6C0` | same |
| `--marigold` | `#FFBE3D` | same |
| `--riso` | `#FF6FA0` | same |
| `--vermilion` | `#FF6B57` | same |
| `--leaf` | `#6CCB7A` | same |
| `--terracotta` | `#E0835A` — **derived** (the spec gives no dark terracotta) | same |

### Conditions
| | Light | Dark | Light text | Dark text |
|---|---|---|---|---|
| C0 Bare LLM | `#7A7F88` | `#9AA0A8` | `#60656E` | same |
| C1 Retrieval | `#3A6EA5` | `#0B94E7` | `#31659C` | same |
| C2 Tools | `#1E2A78` | `#8265A3` | same | `#9A7DBD` |
| C3 Self-verify | `#00727A` | `#2C8766` | `#006F77` | `#419977` |
| C4 Guardrail | `#C4780A` | `#B16A08` | `#9A5100` | `#C17924` |

**Validator results (dataviz `validate_palette.js`, all pairs).** The specified light set fails: C1 `#3A6EA5` and
C3 `#00727A` are ΔE 8.3 apart for normal vision (floor 15) and C0 is grey by design. The colours are kept as specified;
no chart relies on colour alone — every chart row and card is labelled C0–C4 in ink text. *Suggested fix if wanted:*
move C3 toward green (e.g. `#2C8766`) to separate it from C1. The spec gives no dark condition colours; the dark set
is the one validated in M8 (re-checked against `#151922`: CVD ΔE ≥ 8.8, normal-vision ΔE ≥ 15.8, contrast ≥ 3:1).

### Species stripes
BOV indigo · CAP leaf · AVI marigold · CAN terracotta · FEL peacock (all pigments; no extra hues).

### Contrast
`npm run check:contrast` checks every text token (ink, graphite, all `-text` twins, all `c*-text`) against bg,
surface, raised and sunk, text on filled pigments, and the focus ring (3:1), in both themes. All pass.

## Type
- **Instrument Serif** — display and big numbers. Sizes `--display-sm` 40, `--display` 56 (page titles),
  `--display-lg` 72 (Scorecard hero); tracking −0.015em.
- **IBM Plex Sans** — UI (400/500/600). **IBM Plex Mono** — IDs, data, traces, meters.
- Section labels (`.eyebrow`, `.sc-h2`, `.sc-h3`): `font-variant-caps: all-small-caps`, letter-spacing 0.1em.
- Tabular numerals everywhere; `text-wrap: balance` on all headings. Fonts self-hosted via `@fontsource`.
- Body scale 11 / 12.5 / 14 / 16 / 22 px.

## Shape and surface
1px hairlines; radius 2–6px, never more; flat surfaces; no soft shadows. Thin scrollbars (rule track, graphite
thumb). Crop marks on panes, tiles and figures.

## Effects library

| # | Effect | How | Where it is used |
|---|---|---|---|
| 1 | **Risograph misregistration** | `.misreg`: two zero-blur `text-shadow` ghosts, riso-pink left / peacock right, offset `--misreg` 1.5px; settles from 6px on load via registered `--mis`; widens on hover. Display type only — never body text; removed in print. | Page titles (`PageTitle`), Bench case title, Scorecard hero numbers, Overview headline numbers |
| 2 | **Halftone shading** | `.halftone::after`: radial dot screen masked by a linear fade (patterns.css); SVG `<pattern>` dots in charts. Patterns only, never washes. | Active / running condition header, empty-state ladder, Scorecard CI bands (dot-and-whisker), print |
| 3 | **Ink stamps** | `filter: url(#ink-rough)` — `feTurbulence` + `feDisplacementMap` + speckle knock-out (`InkDefs`, mounted once); faint 1px bleed ring; per-stamp tilt −2…−5°; stamp-down with overshoot. | Condition cards, Review, Runs compare, Case dossier history |
| 4 | **Specimen tags** | Luggage shape via `clip-path` chamfer; punched hole via radial `mask-image` through the species stripe; mono ID; species glyph. | Case list, case header, Cases table, dossier, everywhere a case ID appears |
| 5 | **Hand-drawn underline** | `InkUnderline`: one uneven SVG path in riso-pink, `pathLength=1`, draws in via `stroke-dashoffset` (scroll-linked on Overview/Study). | Active nav item; every § section heading (`SectionTitle`) |
| 6 | **Instrument readouts** | `.meter`: segmented VU-style meter on an ink face — marigold segments light as results land (vermilion on error), ≤ 40 segments; hairline gauge animated through registered `--fill`; % readout counts via registered `--count`. `.led`: marigold pulse while running, leaf done, vermilion error. | Run bar; deck tabs, condition card headers, coach-mark pips, dossier history |
| 7 | **Ablation-ladder toggles** | `AblationLadder`: four mechanical switches per condition; knobs flip on in sequence with a click-like overshoot; track in the condition pigment. SVG version on Study Design. | Condition cards, Scorecard legend & hero, Overview, Study Design diagram, empty states |
| 8 | **Paper grain & graph paper** | Grain: SVG noise overlay at 4% (3.5% dark). Graph paper: 8px minor / 40px major lines (patterns.css). | Grain on every page; graph paper behind the Bench |
| 9 | **Keyboard caps** | Global `kbd`: physical key with 2px darker bottom edge; `useKeyPressFeedback` presses the matching on-screen key when the shortcut is typed. | Run bar (R), Reveal gold (G), empty states, coach marks, shortcut sheet, palette |
| 10 | **Mechanical buttons** | `.btn`: 2px darker bottom edge; on press `translateY(1px)` and the edge darkens. No glow, no bloom. | Every button |

Supporting pieces: § section heads (CSS counter + underline), crop marks, drawn tick-boxes, row ink bars, chart
reading band, paper-slip toasts (perforated edge mask, slight tilt), static marigold "running" rule.

## Modern CSS
- **View Transitions** (`lib/viewTransition.ts`, `motion.css`): route changes (nav links and palette use
  `viewTransition`; the page region rises in), case switching (case pane slides), theme toggle (circular reveal from
  the toggle button). Fallback where unsupported: the motion route fade-rise. Skipped under reduced motion.
- **Scroll-driven animations** (`animation-timeline: view()`): Overview and Study Design sections rise in and their
  underlines draw as they enter. Progressive enhancement inside `@supports`.
- **Container queries**: condition cards (`container: ccard`) stack their status line and grid the answer pills below
  330px and show full advice above 520px.
- **`:has()`**: a card holding a danger stamp gets a vermilion edge; the deck header turns marigold while any card
  runs; ticked case rows get a marigold edge.
- **`@property`**: `--count` (count-up numbers), `--fill` (meter gauge), `--mis` (misregistration settle).

## Motion
Durations 120 / 180 / 260 / 320 ms; one easing `cubic-bezier(0.2, 0.8, 0.2, 1)`. Shared-layout sliding selection in
the case list and nav; staggered card entrance; trace lines type in one after another (stepped clip); Scorecard
numbers count up, whiskers draw, halftone bands fade in; stamps land one by one. **Reduced motion:** duration tokens
→ 0, `MotionConfig reducedMotion="user"`, View Transitions skipped, trace typing off, LED pulse off. The LED pulse while
a result is in flight is the only loop (it stops when the result lands); the old sweeping scan line is now a static rule.

## Eye-catching moments
- **Bench case header**: specimen tag, a 40px misregistered serif title (the breed), and the signalment as an
  inked data strip with tick marks.
- **Running a case**: card headers light up in marigold halftone with pulsing LEDs, the meter fills segment by segment,
  stamps land one by one.
- **Scorecard hero**: three 72px numbers — false-safe rate, under-triage rate, top-3 accuracy — for the best condition
  (fewest dangerous errors, then highest top-3) against C0, with deltas; halftone-shaded dot-and-whisker charts below.
- **Empty states**: the five conditions drawn as rows of real toggle switches on halftone, with "press R" in key caps.

## UX
Compare mode (2–3 conditions; cards scroll in sync; differing answers get a marigold underline) · Case dossier
drawer (full case, gold answer with clickable citations, every past result across runs from `GET /api/results?case_id=`) ·
first-run coach marks (4 steps, non-blocking, Esc/Skip, remembered in `localStorage`) · density toggle (Settings and
palette) · print stylesheet (Scorecard → one-page A4 lab report) · paper-slip toasts.

## Responsive
≥ 1440px three resizable Bench panes · 1024–1439px case list in a drawer, sidebar collapsed below 1280px ·
< 1024px stacked panes with condition tabs.

## Keyboard
Ctrl/⌘ K palette · ? shortcut sheet · Bench J/K, X, R, Shift+R, 1–5, G · Review 1, 2, N. Never while typing.

## Known deviations
- Gold answer reveals with a fade-rise (no blur-to-clear: `blur(` is banned).
- Dark terracotta and dark condition colours are derived (not in the spec); light C1/C3 fail the CVD validator as noted.

## Banned (anti-AI rules)
Glassmorphism, `backdrop-filter`, `blur(`; decorative colour gradients and gradient text; neon glows, large soft
shadows; emoji, sparkle or "AI" icons; generic logo squares, centred hero sections; bubbly over-rounded cards; default
Tailwind/shadcn/chart styling; the Inter font; marketing copy; looping attention-grabbing animation, parallax, floating
blobs. **Exception:** gradient functions only for technical patterns, only in `src/styles/patterns.css`.

`npm run check:style` enforces this (plus: colour literals only in `tokens.css`, `text-shadow` only in
`effects.css`, `infinite` only for the LED pulse). It skips `patterns.css` and fails everywhere else.
