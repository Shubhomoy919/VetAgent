import type { CSSProperties } from "react";
import { useTheme } from "../../app/theme";
import { contrastRatio, grade } from "../../lib/contrast";
import palette from "../../styles/palette.generated.json";
import "./palette.css";

type ThemePalette = { label: string; dark: boolean; tokens: Record<string, string> };
const PALETTE = palette as Record<string, ThemePalette>;

const INKS = ["pink", "sunflower", "orange", "cornflower", "violet", "mint", "madder"] as const;
const GROUPS: { title: string; tokens: string[] }[] = [
  { title: "Ground and text", tokens: ["bg", "rule", "text", "text-body", "text-muted", "text-dim", "text-on-ink"] },
  { title: "Paper", tokens: ["paper", "paper-text", "paper-muted"] },
  { title: "Inks", tokens: INKS.flatMap((i) => [`ink-${i}`, `ink-${i}-55`, `ink-${i}-25`]) },
  { title: "Paper inks", tokens: ["paper-orange", "paper-cornflower", "paper-violet", "paper-mint", "paper-sunflower", "paper-madder", "paper-stamp-green"] },
  { title: "Status and interaction", tokens: ["safe", "unsafe", "caution", "info", "running", "focus-ring", "safe-paper", "unsafe-paper"] },
];
const CONDS = ["c0", "c1", "c2", "c3", "c4"] as const;

function Badge({ r, large = false }: { r: number; large?: boolean }) {
  const g = grade(r);
  const pass = large ? r >= 3 : r >= 4.5;
  return (
    <span className="pal-badge mono" data-pass={pass}>
      {r.toFixed(2)}:1 {pass ? (large ? "AA large" : "AA") : g === "AA large" ? "large only" : "fail"}
    </span>
  );
}

/** Settings → Palette: every token of the current theme as a labelled swatch, the condition colours on
 *  the ground and on paper, and sample text on every ink with its contrast ratio and an AA badge.
 *  Values come from the generated palette (the same source as tokens.css). */
export function Palette() {
  const { theme } = useTheme();
  const p = PALETTE[theme];
  if (!p) return null;
  const t = p.tokens;
  const hex = (k: string) => t[k] ?? "";
  return (
    <section className="pal" aria-label="Palette" data-testid="palette">
      <header className="pal-head">
        <h2 className="sc-h3">Palette · {p.label}</h2>
        <p className="pal-note">Swatches show the live tokens; ratios are computed from the generated values.</p>
      </header>

      {GROUPS.map((g) => (
        <div key={g.title} className="pal-group">
          <h3 className="pal-title">{g.title}</h3>
          <ul className="pal-swatches">
            {g.tokens.map((k) => (
              <li key={k} className="pal-sw">
                <span className="pal-chip" style={{ background: `var(--${k})` } as CSSProperties} />
                <span className="pal-name mono">--{k}</span>
                <span className="pal-hex mono">{hex(k)}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}

      <div className="pal-group">
        <h3 className="pal-title">Conditions on the ground and on paper</h3>
        <div className="pal-conds">
          <div className="pal-strip pal-on-ground">
            {CONDS.map((c) => (
              <span key={c} className="pal-cond">
                <span className="pal-dot" style={{ background: `var(--${c})` }} />
                <span className="mono">{c.toUpperCase()}</span>
                <Badge r={contrastRatio(hex(c), hex("bg"))} large />
              </span>
            ))}
          </div>
          <div className="pal-strip pal-on-paper">
            {CONDS.map((c) => (
              <span key={c} className="pal-cond">
                <span className="pal-dot" style={{ background: `var(--${c}-paper)` }} />
                <span className="mono">{c.toUpperCase()}</span>
                <Badge r={contrastRatio(hex(`${c}-paper`), hex("paper"))} large />
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="pal-group">
        <h3 className="pal-title">Text on every ink</h3>
        <ul className="pal-samples">
          {INKS.map((i) => {
            const r = contrastRatio(hex("text-on-ink"), hex(`ink-${i}`));
            return (
              <li key={i} className="pal-sample" style={{ background: `var(--ink-${i})` }}>
                <span className="pal-sample-text">{i === "madder" ? "Marks only" : "Sample text"}</span>
                <Badge r={r} />
                {i === "madder" && <span className="pal-rule mono">never behind small text</span>}
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
