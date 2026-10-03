# Specimen — design system

The feel: a precise field-lab instrument and lab notebook. Calm, exact, data-dense, distinctive.
Tokens live in `frontend/src/app/tokens.css`; this file is the reference.

## Colour

### Light — "Bone & Indigo"
| Token | Hex | Use |
|---|---|---|
| `--bg` (bone) | `#F3EFE6` | page background |
| `--surface` (paper) | `#FBF9F4` | panes, sidebar, top bar |
| `--surface-sunk` | `#ECE7DB` | banner, inset wells (derived) |
| `--ink` | `#14161A` | primary text |
| `--ink-2` (graphite) | `#5A5F68` | secondary text, labels |
| `--rule` | `#DDD6C8` | 1px hairlines |
| `--rule-strong` | `#C9C0AE` | hover hairlines, hollow marks (derived) |
| `--indigo` | `#23306B` | primary accent, focus, ESCALATED |
| `--turmeric` | `#D99A1E` | demo mode, running scan line |
| `--terracotta` | `#B4532A` | warnings |
| `--vermilion` | `#B3261E` | FALSE-SAFE, UNDER-TRIAGE, errors |
| `--leaf` | `#2F6B3B` | CORRECT, live |

### Dark — "Night Lab"
| Token | Hex |
|---|---|
| `--bg` | `#0F1115` |
| `--surface` | `#161A21` |
| `--ink` | `#E9E6DF` |
| `--ink-2` | `#9AA0A8` |
| `--rule` | `#262B33` |
| `--indigo` | `#8E9BEA` |
| `--turmeric` | `#E6B04A` |
| `--vermilion` | `#F07167` |
| `--leaf` | `#6FBF7F` |

`--surface-sunk #12151B`, `--rule-strong #343A44` and `--terracotta #D9774C` are derived for dark.

### Conditions
| | Light | Dark (derived for contrast) |
|---|---|---|
| C0 Bare LLM | `#6B6F76` | `#9AA0A8` |
| C1 Retrieval | `#4A6FA5` | `#7C9CD0` |
| C2 Tools | `#23306B` | `#8E9BEA` |
| C3 Self-verify | `#1F6F6A` | `#5FB3AC` |
| C4 Guardrail | `#9A6B0F` | `#D1A03E` |

The light condition colours are specified; the dark ones are lifted so they stay legible on `#161A21`.

### Species stripes (specimen tags, filter chips — derived from the palette)
| Code | Light | Dark |
|---|---|---|
| BOV | `#23306B` indigo | `#8E9BEA` |
| CAP | `#2F6B3B` leaf | `#6FBF7F` |
| AVI | `#D99A1E` turmeric | `#E6B04A` |
| CAN | `#B4532A` terracotta | `#D9774C` |
| FEL | `#7A5C99` plum (added) | `#B39DD1` |

### Text-contrast token
`--turmeric-ink` (`#8A5F0B` light, `#E6B04A` dark) is used wherever turmeric is *text* (DEMO pill, UNVERIFIED
tag); raw turmeric `#D99A1E` on paper is about 2.3:1 and fails WCAG AA, so it is kept for borders and fills.

## Type
- **Instrument Serif** — page titles, wordmark, big numbers, empty-state headlines.
- **IBM Plex Sans** — all UI text (400/500/600).
- **IBM Plex Mono** — case IDs, condition IDs, JSON, traces, eyebrow labels, pills.
- Tabular numerals everywhere (`font-variant-numeric: tabular-nums`).
- Fonts are self-hosted via `@fontsource` (no CDN dependency).

Scale: 11 / 12.5 / 14 (base) / 16 / 22 / 34 px.

## Shape and surface
- 1px hairlines (`--rule`); radius 3–6px, never more.
- Flat surfaces. No shadows.
- Paper grain: a fixed SVG `feTurbulence` overlay at 3.5–5% opacity.
- Graph paper behind the Bench: SVG pattern, 8px minor / 40px major lines.

## Motion
- Durations 120 / 180 / 260ms; easing `cubic-bezier(0.2, 0.8, 0.2, 1)`.
- Route change: fade-rise 6px. Sidebar selection: shared-layout sliding highlight.
- Lists: 40ms stagger on entrance.
- `prefers-reduced-motion`: `MotionConfig reducedMotion="user"` plus CSS duration tokens set to 0.
- No parallax, blobs or looping animations.

## Signature elements
1. **Specimen tags** — luggage-tag case IDs in mono with a punched hole and species colour stripe. Built:
   `components/Tags.tsx` (with the question-type pill and the UNVERIFIED tag).
2. **Ablation ladder** — Retrieval / Tools / Verify / Guardrail as filled or hollow dots per condition, joined by a hairline. Built: `components/AblationLadder.tsx`.
3. **Verdict stamps** — CORRECT (leaf), FALSE-SAFE / UNDER-TRIAGE / MISSED ESCALATION / WITHDRAWAL ERROR
   (vermilion), ESCALATED (indigo); uppercase mono, 2px border, rotated −3°, stamp-down (scale 1.5→1, 220 ms).
   Built: `components/Stamp.tsx`; verdict logic in `backend/app/scoring/verdict.py`.
4. **Lab-log traces** — numbered vertical timeline with a hairline spine; each step is a mono readout
   (MODEL / TOOL / OWNER / VERIFY / RULE / RETRY, name, latency, tokens) that expands to input/output JSON.
   Streamed steps slide in. Built: `features/bench/TraceLog.tsx`.

Running state: a 2px turmeric scan line crosses the run bar and the active card, only while a run is in
progress (static full-width line under reduced motion). Toasts are sonner in unstyled mode: flat surface, hairline,
turmeric (or vermilion for errors) left edge — no shadows.
5. **Dot-and-whisker charts** — metrics with CIs; headline numbers in Instrument Serif. (M5.)

## Banned
Glassmorphism, `backdrop-filter`, `blur(`, gradients and gradient text, neon glows, large soft shadows,
emoji, sparkle/"AI" icons, generic logo squares, centred hero sections, bubbly over-rounded cards,
default Tailwind/shadcn/chart styling, the Inter font, marketing copy.

Check with:
```
grep -rniE "backdrop-filter|blur\(|gradient|\bInter\b|box-shadow" frontend/src
```
