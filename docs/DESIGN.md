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
1. **Specimen tags** — luggage-tag case IDs in mono, species code, colour stripe. (Empty outline in M1; filled in M2.)
2. **Ablation ladder** — Retrieval / Tools / Verify / Guardrail as filled or hollow dots per condition, joined by a hairline. Built: `components/AblationLadder.tsx`.
3. **Verdict stamps** — CORRECT (leaf), FALSE-SAFE / UNDER-TRIAGE (vermilion), ESCALATED (indigo); uppercase mono, 2px border, rotated about -3°, stamp-down animation. (M4.)
4. **Lab-log traces** — numbered vertical timeline; tool calls as mono readouts with latency and tokens. (M4.)
5. **Dot-and-whisker charts** — metrics with CIs; headline numbers in Instrument Serif. (M5.)

## Banned
Glassmorphism, `backdrop-filter`, `blur(`, gradients and gradient text, neon glows, large soft shadows,
emoji, sparkle/"AI" icons, generic logo squares, centred hero sections, bubbly over-rounded cards,
default Tailwind/shadcn/chart styling, the Inter font, marketing copy.

Check with:
```
grep -rniE "backdrop-filter|blur\(|gradient|\bInter\b|box-shadow" frontend/src
```
