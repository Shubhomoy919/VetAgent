"""Generate src/styles/tokens.css — "The Field Station" (three themes). Run: npm run tokens

Each theme lists its specified colours. From those the generator derives:
  * *-text twins: the same hue, shifted only in OKLCH lightness until the colour reaches 4.6:1 as text
    on every background of the theme (bg, surface, raised, sunk);
  * c*-block (Bone & Block): condition block fills, deepened in lightness until bone text on them is AA;
  * the oklch @supports layer (same colours).
Hex values come first as the fallback. scripts/check-contrast.mjs verifies the result.
"""
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


def mix(a, b, p):  # srgb color-mix(a p, b)
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


def ok(h):
    L, C, H = to_oklch(h)
    return f"oklch({L * 100:.1f}% {C:.3f} {H:.1f})"


# ---------------------------------------------------------------- themes
# Slots: bg (ground), sidebar, surface, raised, rule (hairline), grid, ink, ink-2,
# pigments: indigo, peacock, marigold, riso, vermilion (unsafe), leaf (safe), terracotta (caution),
# plus theme pigments (cyan, madder, ochre, forest) and conditions c0–c4.

THEMES = {
    "cyanotype": dict(
        dark=True, label="Cyanotype",
        base=dict(bg="#0C2F57", sidebar="#08223F", surface="#10396A", raised="#154679", rule="#2B5C8F",
                  grid="#1A4475", ink="#EAF2F8", **{"ink-2": "#A8C3DA"}),
        pig=dict(indigo="#9CC3FF", cyan="#BFE6FF", peacock="#5FD3C8", marigold="#FFB627", riso="#FF6F9C",
                 vermilion="#E2574C", madder="#E2574C", leaf="#7FD1A1", terracotta="#F08A5D", ochre="#FFB627",
                 forest="#7FD1A1",
                 c0="#9FB3C8", c1="#7FB2FF", c2="#C5D4FF", c3="#5FD3C8", c4="#FFB627"),
        chrome=dict(sidebar_ink="#EAF2F8", topbar_bg="#08223F", topbar_ink="#EAF2F8", topbar_accent="#FFB627"),
        zones=dict(bench="cyan", scorecard="peacock", data="marigold", runs="riso", about="ink-2"),
        derived_ink="#08223F",
    ),
    "bone-block": dict(
        dark=False, label="Bone & Block",
        base=dict(bg="#F2EDE3", sidebar="#1E2A78", surface="#FBF8F2", raised="#FFFFFF", rule="#D9D1C1",
                  grid="#E4DCCB", ink="#121418", **{"ink-2": "#575C66"}),
        pig=dict(indigo="#1E2A78", cyan="#3A6EA5", peacock="#00727A", marigold="#F2A007", riso="#E8447C",
                 vermilion="#D23B1F", madder="#D23B1F", leaf="#2E7D32", terracotta="#B4532A", ochre="#C4780A",
                 forest="#2E7D32",
                 c0="#575C66", c1="#3A6EA5", c2="#1E2A78", c3="#00727A", c4="#C4780A"),
        chrome=dict(sidebar_ink="#F2EDE3", topbar_bg="#121418", topbar_ink="#F2EDE3", topbar_accent="#F2A007"),
        zones=dict(bench="indigo", scorecard="peacock", data="marigold", runs="riso", about="ink-2"),
        derived_ink="#121418",
    ),
    "kalamkari": dict(
        dark=False, label="Kalamkari",
        base=dict(bg="#F4EBDD", sidebar="#EFE3CF", surface="#FBF5EA", raised="#FFFCF5", rule="#D8C7A8",
                  grid="#E6D8BF", ink="#1C1A17", **{"ink-2": "#5E5548"}),
        pig=dict(indigo="#1F2B5E", cyan="#1F2B5E", peacock="#2D5A3D", marigold="#C98A1B", riso="#B83A62",
                 vermilion="#9E2B25", madder="#9E2B25", leaf="#2D5A3D", terracotta="#A8521F", ochre="#C98A1B",
                 forest="#2D5A3D",
                 c0="#6E665C", c1="#1F2B5E", c2="#2D5A3D", c3="#C98A1B", c4="#9E2B25"),
        chrome=dict(sidebar_ink="#1C1A17", topbar_bg="#FBF5EA", topbar_ink="#1C1A17", topbar_accent="#9E2B25"),
        zones=dict(bench="indigo", scorecard="forest", data="ochre", runs="madder", about="ink-2"),
        derived_ink="#1C1A17",
    ),
}
DEFAULT = "cyanotype"
SPECIES = dict(bov="indigo", cap="leaf", avi="marigold", can="terracotta", fel="peacock")

out = [
    "/* The Field Station — three themes. GENERATED by scripts/gen_tokens.py; edit there, not here.",
    "   Hex values first (fallback), then an @supports layer in oklch with the same colours.",
    "   Pigments are fills/marks; *-text twins are the same hue shifted in OKLCH lightness to reach",
    "   WCAG AA as text on every background of the theme. Checked by scripts/check-contrast.mjs. */",
    "",
]
summary = {}
for name, t in THEMES.items():
    b, p, ch = t["base"], t["pig"], t["chrome"]
    dark = t["dark"]
    sunk = mix(b["ink"], b["bg"], 0.05)
    bgs = [b["bg"], b["surface"], b["raised"], sunk]
    vals = dict(b)
    vals.update(p)
    for k, h in p.items():
        vals[f"{k}-text"] = shift_until(h, lambda c: min(cr(c, x) for x in bgs) >= 4.6, lighter=dark)
    vals["sidebar-ink"] = ch["sidebar_ink"]
    vals["sidebar-ink-2"] = shift_until(mix(ch["sidebar_ink"], b["sidebar"], 0.72), lambda c: cr(c, b["sidebar"]) >= 4.6,
                                        lighter=cr(ch["sidebar_ink"], "#000000") > cr(ch["sidebar_ink"], "#ffffff"))
    vals["topbar-bg"] = ch["topbar_bg"]
    vals["topbar-ink"] = ch["topbar_ink"]
    vals["topbar-accent"] = shift_until(ch["topbar_accent"], lambda c: cr(c, ch["topbar_bg"]) >= 4.6,
                                        lighter=lum(ch["topbar_bg"]) < 0.2)
    bone = b["bg"]
    for i in range(5):
        c = p[f"c{i}"]
        if name == "bone-block":
            vals[f"c{i}-block"] = shift_until(c, lambda x: cr(x, bone) >= 4.6, lighter=False)
        else:
            vals[f"c{i}-block"] = c
    vals["scrim-base"] = t["derived_ink"]
    vals["shadow"] = shift_until(mix(t["derived_ink"], b["bg"], 0.55), lambda x: True, lighter=False)

    sel = f':root[data-theme="{name}"]' if name != DEFAULT else f':root,\n:root[data-theme="{name}"]'
    lines = [f"{sel} {{", f"  color-scheme: {'dark' if dark else 'light'};", ""]
    lines += [f"  --{k}: {v.lower()};" for k, v in vals.items()]
    lines += [
        "",
        "  /* Derived (color-mix only) */",
        "  --surface-sunk: color-mix(in srgb, var(--ink) 5%, var(--bg));",
        "  --rule-strong: color-mix(in srgb, var(--ink) 16%, var(--rule));",
        "  --on-accent: var(--surface);",
        f"  --on-block: {'var(--bg)' if name == 'bone-block' else 'var(--ink)'};",
        "  --focus: var(--riso-text);",
        f"  --on-marigold: var(--{'bg' if dark else 'ink'});",
        "  --scrim: color-mix(in srgb, var(--scrim-base) 45%, transparent);",
        "  --selection: color-mix(in srgb, var(--marigold) 35%, transparent);",
        "  --grid-minor: color-mix(in srgb, var(--grid) 60%, transparent);",
        "  --grid-major: var(--grid);",
        "  --halftone-ink: color-mix(in srgb, var(--ink) 18%, transparent);",
        f"  --grain-opacity: {0.05 if dark else 0.045};",
        f"  --meter-face: var(--{'sidebar' if dark else 'ink'});",
        "  --meter-off: color-mix(in srgb, var(--ink-2) 30%, var(--meter-face));",
        "  /* Hard offset print shadow: 3px 3px 0 in a darker tone of the ground — never blurred. */",
        "  --shadow-hard: 3px 3px 0 var(--shadow);",
        f"  --shadow-press: 2px 2px 0 var(--{'sidebar' if dark else 'ink'});",
        f"  --theme-is-dark: {1 if dark else 0};",
        "  /* Page colour zones (html[data-zone] picks one) */",
    ]
    lines += [f"  --zone-{z}: var(--{v});" for z, v in t["zones"].items()]
    lines += ["  /* Species stripes */"]
    lines += [f"  --sp-{k}: var(--{v});" for k, v in SPECIES.items()]
    lines += ["}", "", "@supports (color: oklch(0% 0 0)) {", f"  {sel.replace(chr(10), ' ')} {{"]
    lines += [f"    --{k}: {ok(v)};" for k, v in vals.items()]
    lines += ["  }", "}", ""]
    out += lines
    summary[name] = {k: v for k, v in vals.items() if (k.endswith("-text") and v != vals[k[:-5]]) or (k.endswith("-block") and v != vals[k[:-6]])}

# Theme-independent swatch previews for the theme switcher (ground, accent, ink of each theme).
sw = [":root {"]
for name, t in THEMES.items():
    sw += [f"  --sw-{name}-ground: {t['base']['bg'].lower()};",
           f"  --sw-{name}-side: {t['base']['sidebar'].lower()};",
           f"  --sw-{name}-accent: {t['pig']['marigold'].lower()};",
           f"  --sw-{name}-ink: {t['base']['ink'].lower()};"]
sw += ["}", ""]
out += sw
out.append(pathlib.Path("scripts/tokens.static.css").read_text(encoding="utf-8"))
pathlib.Path("src/styles/tokens.css").write_text("\n".join(out), encoding="utf-8", newline="\n")
for name, s in summary.items():
    print(name, s)
