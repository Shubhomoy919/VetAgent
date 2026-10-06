"""Generate src/styles/tokens.css — Riso Black (default), Cyanotype, Kalamkari. Run: npm run tokens

Every theme defines the SAME semantic token names; components use only these.
Specified values are written as given. Derived values:
  * *-text twins: same hue, OKLCH lightness shifted until 4.6:1 as text on every background of the theme;
  * inks used as fills under --text-on-ink are shifted in lightness until that text is AA (reported);
  * paper inks (marks on paper) are shifted until 3:1 against paper (reported);
  * an @supports oklch layer repeats every hex colour.
scripts/check-contrast.ts verifies every text/background pair the UI uses.
"""
import json
import math
import pathlib

# ---------------------------------------------------------------- colour maths


def h2rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def delin(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def to_oklch(h):
    r, g, b = map(lin, h2rgb(h))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def from_oklch(L, C, H):
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
           -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
           -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s]
    return [delin(x) if x > 0 else 0 for x in rgb]


def in_gamut(rgb):
    return all(-1e-4 <= x <= 1 + 1e-4 for x in rgb)


def hexof(rgb):
    return "#" + "".join(f"{round(min(max(x, 0), 1) * 255):02x}" for x in rgb)


def lum(h):
    return sum(w * lin(c) for w, c in zip((0.2126, 0.7152, 0.0722), h2rgb(h)))


def cr(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def mix(a, b, p):
    return hexof([x * p + y * (1 - p) for x, y in zip(h2rgb(a), h2rgb(b))])


def shift_until(h, ok, lighter):
    """Same hue; step OKLCH lightness (reducing chroma only to stay in gamut) until ok(candidate)."""
    if ok(h):
        return h
    L, C, H = to_oklch(h)
    for step in range(1, 100):
        L2 = L + (0.01 * step if lighter else -0.01 * step)
        c = C
        while c > 0 and not in_gamut(from_oklch(L2, c, H)):
            c -= 0.004
        cand = hexof(from_oklch(L2, max(c, 0), H))
        if ok(cand):
            return cand
    raise SystemExit(f"cannot derive a passing variant of {h}")


def oklch_str(h):
    L, C, H = to_oklch(h)
    return f"oklch({L * 100:.1f}% {C:.3f} {H:.1f})"


INKS = ["pink", "sunflower", "orange", "cornflower", "violet", "mint", "madder"]
COND_PAPER = {"c0": "orange", "c1": "cornflower", "c2": "violet", "c3": "mint", "c4": "sunflower"}

# ---------------------------------------------------------------- themes
THEMES = {
    "riso-black": dict(
        label="Riso Black", dark=True,
        base={
            "bg": "#000000", "sidebar": "#000000", "surface": "#000000", "raised": "#000000",
            "rule": "#2A2A2A", "rule-soft": "rgba(244,239,230,.13)",
            "grid-minor": "rgba(255,255,255,.035)", "grid-major": "rgba(255,255,255,.06)",
            "text": "#F4EFE6", "text-body": "#E4DFD6", "text-muted": "#B8B2A8", "text-dim": "#8A847A",
            "text-on-ink": "#10201F",
            "paper": "#F5EBDD", "paper-text": "#10201F", "paper-muted": "#4B5655", "paper-rule": "rgba(16,32,31,.14)",
        },
        inks=dict(pink="#FF4F9A", sunflower="#FFC933", orange="#FF7A2F", cornflower="#5B8CFF",
                  violet="#9B7BFF", mint="#6EE7C8", madder="#E5484D"),
        paper_inks={"orange": "#E8601C", "cornflower": "#3B6CF0", "violet": "#7A55F0", "mint": "#1FAE8C",
                    "sunflower": "#D99A00", "madder": "#C23A2E", "stamp-green": "#1F8A5B"},
        cond=dict(c0="orange", c1="cornflower", c2="violet", c3="mint", c4="sunflower"),
        topbar_accent="sunflower",
    ),
    "cyanotype": dict(
        label="Cyanotype", dark=True,
        base={
            "bg": "#0C2F57", "sidebar": "#08223F", "surface": "#10396A", "raised": "#154679",
            "rule": "#2B5C8F", "rule-soft": "rgba(234,242,248,.14)",
            "grid-minor": "rgba(191,230,255,.05)", "grid-major": "rgba(191,230,255,.09)",
            "text": "#EAF2F8", "text-body": "#DCE8F2", "text-muted": "#A8C3DA", "text-dim": "#93B1CB",
            "text-on-ink": "#08223F",
            "paper": "#EAF2F8", "paper-text": "#0C2F57", "paper-muted": "#3D5C7D", "paper-rule": "rgba(12,47,87,.16)",
        },
        inks=dict(pink="#FF6F9C", sunflower="#FFB627", orange="#F08A5D", cornflower="#7FB2FF",
                  violet="#B9A6FF", mint="#5FD3C8", madder="#E2574C"),
        paper_inks={"orange": "#C2551B", "cornflower": "#2F5FC4", "violet": "#6A48D6", "mint": "#12806B",
                    "sunflower": "#A86F00", "madder": "#B3261E", "stamp-green": "#1F7A4F"},
        cond={"c0": "#9FB3C8", "c1": "#7FB2FF", "c2": "#C5D4FF", "c3": "#5FD3C8", "c4": "#FFB627"},
        topbar_accent="sunflower",
    ),
    "kalamkari": dict(
        label="Kalamkari", dark=False,
        base={
            "bg": "#F4EBDD", "sidebar": "#EFE3CF", "surface": "#FBF5EA", "raised": "#FFFCF5",
            "rule": "#D8C7A8", "rule-soft": "rgba(28,26,23,.12)",
            "grid-minor": "rgba(28,26,23,.05)", "grid-major": "rgba(28,26,23,.09)",
            "text": "#1C1A17", "text-body": "#2B2823", "text-muted": "#5E5548", "text-dim": "#6A6156",
            "text-on-ink": "#FBF5EA",
            "paper": "#FFFCF5", "paper-text": "#1C1A17", "paper-muted": "#5E5548", "paper-rule": "rgba(28,26,23,.14)",
        },
        inks=dict(pink="#B83A62", sunflower="#C98A1B", orange="#A8521F", cornflower="#1F2B5E",
                  violet="#5B3F7A", mint="#2D5A3D", madder="#9E2B25"),
        paper_inks={"orange": "#8E4317", "cornflower": "#1F2B5E", "violet": "#4A3266", "mint": "#24492F",
                    "sunflower": "#8F5400", "madder": "#8A241F", "stamp-green": "#2D5A3D"},
        cond={"c0": "#6E665C", "c1": "#1F2B5E", "c2": "#2D5A3D", "c3": "#C98A1B", "c4": "#9E2B25"},
        topbar_accent="madder",
    ),
}
DEFAULT = "riso-black"
SPECIES = dict(can="orange", fel="violet", bov="cornflower", cap="mint", avi="sunflower")
# Page zones: each section has its own ink pair (InkBleed clouds, watermark, nav marker tint).
ZONES = dict(bench=("pink", "cornflower"), scorecard=("mint", "violet"), data=("sunflower", "orange"),
             runs=("pink", "violet"), overview=("orange", "pink"), about=("cornflower", "mint"))

adjustments = []
palette_json = {}
out = [
    "/* VetAgentBench-IN tokens — Riso Black (default), Cyanotype, Kalamkari.",
    "   GENERATED by scripts/gen_tokens.py; edit there, not here. Every theme defines the same semantic",
    "   names; components use only those. Hex first, then an @supports oklch layer with the same colours.",
    "   Checked by scripts/check-contrast.ts. */",
    "",
]
for name, t in THEMES.items():
    b = dict(t["base"])
    dark = t["dark"]
    sunk = mix(b["text"], b["bg"], 0.05)
    bgs = [b["bg"], b["surface"], b["raised"], sunk]
    on_ink = b["text-on-ink"]
    vals = dict(b)
    # Dimmest text must still read on every panel.
    vals["text-dim"] = shift_until(b["text-dim"], lambda x: min(cr(x, g) for g in bgs) >= 4.6, lighter=dark)
    if vals["text-dim"].lower() != b["text-dim"].lower():
        adjustments.append(f"{name}: --text-dim {b['text-dim']} -> {vals['text-dim']} (AA on every panel)")

    for k, h in t["inks"].items():
        # Madder is never a background for small text (colour rule A3), so it keeps its exact value.
        fixed = h if k == "madder" else shift_until(h, lambda c: cr(c, on_ink) >= 4.6, lighter=lum(on_ink) < 0.2)
        if fixed.lower() != h.lower():
            adjustments.append(f"{name}: --ink-{k} {h} -> {fixed} (text-on-ink AA on the fill)")
        vals[f"ink-{k}"] = fixed
    for k, h in t["paper_inks"].items():
        fixed = shift_until(h, lambda c: cr(c, b["paper"]) >= 3.1, lighter=lum(b["paper"]) < 0.2)
        if fixed.lower() != h.lower():
            adjustments.append(f"{name}: --paper-{k} {h} -> {fixed} (3:1 mark on paper)")
        vals[f"paper-{k}"] = fixed

    def ink(k):
        return vals[f"ink-{k}"]

    for c, v in t["cond"].items():
        h = v if v.startswith("#") else ink(v)
        # Condition colours are chart marks (3:1 on the ground) and fills under text-on-ink (AA).
        fixed = shift_until(h, lambda x: cr(x, b["bg"]) >= 3.0 and cr(x, on_ink) >= 4.6, lighter=lum(on_ink) < 0.2)
        if fixed.lower() != h.lower():
            adjustments.append(f"{name}: --{c} {h} -> {fixed} (chart mark 3:1 and text-on-ink AA)")
        h = fixed
        vals[c] = h
        vals[f"{c}-text"] = shift_until(h, lambda x: min(cr(x, g) for g in bgs) >= 4.6, lighter=dark)
        vals[f"{c}-paper"] = vals[f"paper-{COND_PAPER[c]}"]

    sem = dict(safe=ink("mint"), unsafe=ink("madder"), caution=ink("orange"), info=ink("cornflower"),
               running=ink("sunflower"), accent=ink("pink"))
    for k, h in sem.items():
        vals[k] = h
        vals[f"{k}-text"] = shift_until(h, lambda x: min(cr(x, g) for g in bgs) >= 4.6, lighter=dark)
    vals["safe-paper"] = vals["paper-stamp-green"]
    vals["unsafe-paper"] = vals["paper-madder"]
    vals["focus-ring"] = shift_until(ink("pink"), lambda x: min(cr(x, g) for g in bgs) >= 3.0, lighter=dark)

    vals["sidebar-ink"] = b["text"]
    vals["sidebar-ink-2"] = shift_until(b["text-muted"], lambda c: cr(c, b["sidebar"]) >= 4.6, lighter=dark)
    vals["topbar-bg"] = b["sidebar"]
    vals["topbar-ink"] = b["text"]
    readout = mix("#ffffff" if dark else "#000000", b["sidebar"], 0.06)
    vals["readout-bg"] = readout
    vals["topbar-accent"] = shift_until(ink(t["topbar_accent"]), lambda c: min(cr(c, b["sidebar"]), cr(c, readout)) >= 4.6, lighter=dark)
    vals["topbar-ink-2"] = shift_until(b["text-muted"], lambda c: min(cr(c, b["sidebar"]), cr(c, readout)) >= 4.6, lighter=dark)
    vals["hero-bg"] = b["paper"]
    vals["hero-text"] = b["paper-text"]
    vals["hero-text-2"] = b["paper-muted"]
    face = "#000000" if name == "riso-black" else (b["sidebar"] if dark else b["text"])
    vals["meter-face"] = face
    off = mix(b["text-muted"], face, 0.30)
    vals["meter-ink"] = max([b["text"], b["bg"], b["text-muted"]], key=lambda c: cr(c, off))

    # Palette JSON (hex values per theme) for the Settings palette and its contrast badges.
    pj = {k: v.lower() for k, v in vals.items() if v.startswith("#")}
    for k in INKS:
        pj[f"ink-{k}-55"] = mix(vals[f"ink-{k}"], "#000000", 0.55)
        pj[f"ink-{k}-25"] = mix(vals[f"ink-{k}"], "#000000", 0.25)
    pj["unsafe-tint"] = mix(vals["ink-madder"], b["bg"], 0.22)
    palette_json[name] = {"label": t["label"], "dark": dark, "tokens": pj}

    sel = f':root,\n:root[data-theme="{name}"]' if name == DEFAULT else f':root[data-theme="{name}"]'
    lines = [f"{sel} {{", f"  color-scheme: {'dark' if dark else 'light'};", ""]
    lines += [f"  --{k}: {v.lower() if v.startswith('#') else v};" for k, v in vals.items()]
    lines += ["", "  /* Ink tints (55% / 25%), mixed with black */"]
    for k in INKS:
        lines += [f"  --ink-{k}-55: color-mix(in srgb, var(--ink-{k}) 55%, #000);",
                  f"  --ink-{k}-25: color-mix(in srgb, var(--ink-{k}) 25%, #000);"]
    lines += [
        "",
        "  /* Derived semantic tokens */",
        "  --c0-block: var(--c0);",
        "  --c1-block: var(--c1);",
        "  --c2-block: var(--c2);",
        "  --c3-block: var(--c3);",
        "  --c4-block: var(--c4);",
        "  --surface-sunk: color-mix(in srgb, var(--text) 5%, var(--bg));",
        "  /* Madder tint for danger states: madder mixed into the ground, carrying normal text */",
        "  --unsafe-tint: color-mix(in srgb, var(--ink-madder) 22%, var(--bg));",
        "  --rule-strong: color-mix(in srgb, var(--text) 18%, var(--rule));",
        "  --selection: color-mix(in srgb, var(--ink-sunflower) 35%, transparent);",
        "  --nav-active-bg: var(--ink-pink);",
        "  --nav-active-shadow: var(--ink-cornflower);",
        "  --sheet-shadow: var(--ink-pink);",
        "  --scrim: color-mix(in srgb, var(--bg) 70%, transparent);",
        "  --halftone-ink: color-mix(in srgb, var(--text) 16%, transparent);",
        f"  --grain-opacity: {0.05 if dark else 0.045};",
        "  --meter-off: color-mix(in srgb, var(--text-muted) 30%, var(--meter-face));",
        "  /* Hard offset shadows in ink colours only: never black, never blurred */",
        "  --shadow: var(--ink-cornflower-55);",
        "  --shadow-hard: 3px 3px 0 var(--shadow);",
        "  --shadow-press: 2px 2px 0 var(--ink-pink);",
        f"  --theme-is-dark: {1 if dark else 0};",
        "  /* Page zones: an ink pair per section */",
    ]
    for z, (a, bb) in ZONES.items():
        lines += [f"  --zone-{z}: var(--ink-{a});", f"  --zone-{z}-b: var(--ink-{bb});"]
    lines += ["  /* Species tags */"] + [f"  --sp-{k}: var(--ink-{v});" for k, v in SPECIES.items()]
    lines += ["}", "", "@supports (color: oklch(0% 0 0)) {", f"  {sel.replace(chr(10), ' ')} {{"]
    lines += [f"    --{k}: {oklch_str(v)};" for k, v in vals.items() if v.startswith("#")]
    lines += ["  }", "}", ""]
    out += lines

sw = [":root {"]
for name, t in THEMES.items():
    sw += [f"  --sw-{name}-ground: {t['base']['bg'].lower()};",
           f"  --sw-{name}-side: {t['base']['paper'].lower()};",
           f"  --sw-{name}-accent: {t['inks']['pink'].lower()};",
           f"  --sw-{name}-ink: {t['inks']['sunflower'].lower()};"]
sw += ["}", ""]
out += sw
out.append(pathlib.Path("scripts/tokens.static.css").read_text(encoding="utf-8"))
pathlib.Path("src/styles/tokens.css").write_text("\n".join(out), encoding="utf-8", newline="\n")
pathlib.Path("src/styles/palette.generated.json").write_text(json.dumps(palette_json, indent=1) + "\n", encoding="utf-8", newline="\n")
print("adjusted to meet contrast:" if adjustments else "no adjustments needed")
for a in adjustments:
    print("  " + a)
