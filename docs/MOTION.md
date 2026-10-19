# Motion

Only what remains after the black-and-pink simplification. Durations 80–320 ms on one easing,
`cubic-bezier(0.2, 0.8, 0.2, 1)`. Animations touch only `transform`, `opacity`, `clip-path` and
`stroke-dashoffset`. The only loop is the running LED, and only while a result is in flight.

| Element | Animation | Trigger | Duration | Where |
|---|---|---|---|---|
| Route content | Crossfade | Route change | 80 ms out + 80 ms in | `app/Shell.tsx` |
| Active nav marker | Shared-layout slide | Route change | 160 ms | `app/Shell.tsx` |
| Case list selection | Shared-layout slide | Case change (click, J/K) | 200 ms | `features/bench/CaseList.tsx` |
| Page title | Ink-in (clip-path) | Page mount | 260 ms | `components/PageHeader.tsx` |
| Page header rule | Draws across (scaleX) | Page mount | 260 ms | `components/PageHeader.css` |
| Section heading underline | Pink stroke draws (stroke-dashoffset); scroll-linked on Overview / Study | Mount / scroll into view | 320 ms | `styles/effects.css`, `styles/motion.css` |
| Overview / Study sections | Rise into place (scroll-driven) | Scroll into view | scroll-linked | `styles/motion.css` |
| Running LED | Pulse | Result in flight | 900 ms, alternates; stops when the result lands | `styles/effects.css` |
| Running card / run bar | Static running rule scales in | Run starts | 320 ms | `features/bench/run.css` |
| Vital-signs trace | Segments draw in (stroke-dashoffset), staggered | Each streamed step | 260 ms | `components/VitalTrace.css` |
| Trace log | Spine draws down; lines type in | Trace opens / steps stream | 260–320 ms | `features/bench/run.css`, `TraceLog.tsx` |
| Verdict stamp | Stamp down with a small overshoot | Result lands | 260 ms, 120 ms stagger | `components/Stamp.tsx` |
| Dose needle | Sweep with overshoot | Card shows a dose | 320 ms | `components/DoseDial.tsx` |
| Switchboard knob | Flips across with a click-like overshoot | Mount | 200 ms, staggered | `components/Switchboard.tsx`, `features/study/StudyPage.tsx` |
| Scorecard numbers | Count up via registered `--count` | Mount / run change | 320 ms | `styles/effects.css` |
| Dot-and-whisker | Whiskers draw; CI halftone bands fade in | Mount | 260–320 ms | `features/scorecard/DotWhisker.tsx` |
| Gold answer | Fade-rise | G / Reveal | 240 ms | `features/bench/CaseDetail.tsx` |
| Drawers (dossier, passage) | Paper sheet slides in and settles | Open | 320 ms | `components/SideDrawer.tsx`, `PassageDrawer.tsx` |
| `?` help overlay | Fade | `?` | 120 ms | `app/ShortcutHelp.tsx` |
| Key caps | Press down 1px | Matching shortcut | 120 ms | `lib/useKeyPressFeedback.ts`, `styles/effects.css` |
| Buttons | Press down 1px | Pointer down | 120 ms | `styles/controls.css` |

**Reduced motion.** The duration tokens drop to 0 ms, `MotionConfig reducedMotion="user"` applies to every
motion component, and the LED pulse, count-ups, underline draws, typed log lines, trace draw-in and running
rule are switched off. The e2e suite checks that `--dur` is `0ms` under reduced motion.

**Removed:** theme ink-spread transition, View Transitions for routes and cases, the printer-strip pass,
corner-mark draw, coach-mark slip, launcher slide, misregistration settle, develop washes, plate morph,
registration-mark hover draw, chart crosshair.

## Keyframe registry

Every `@keyframes` in the stylesheets, each defined once. `npm --prefix frontend run check:motion` fails if a
keyframe is missing here, defined twice, loops (other than the LED), animates a property outside the list
above, or uses a literal duration outside 80–320 ms.

| Keyframes | Animates | Used by |
|---|---|---|
| `ph-rule` | transform (scaleX) | Page header rule |
| `vt-draw` | stroke-dashoffset | Vital-signs trace segments |
| `scan-in` | transform (scaleX) | Running card / run bar rule |
| `log-spine` | transform (scaleY) | Trace log spine |
| `type-in` | clip-path | Trace log lines typing in |
| `ink-draw` | stroke-dashoffset | Section heading underline |
| `led-pulse` | opacity, 900 ms, alternates (the only loop) | Running LED |
| `count-up` | `--count` | Scorecard numbers |
| `sec-rise` | opacity, transform | Overview / Study sections (scroll-driven) |
