import type { MouseEvent } from "react";
import { THEMES, applyTheme, useTheme, type Theme } from "../app/theme";
import { withViewTransition } from "../lib/viewTransition";
import "./ThemeSwatches.css";

/** 3-way theme switcher: a printed swatch per theme (ground, sidebar block, marigold, ink).
 *  Switching spreads the new theme like ink from the clicked swatch (View Transitions). */
export function ThemeSwatches({ size = "sm" }: { size?: "sm" | "lg" }) {
  const { theme } = useTheme();
  const pick = (id: Theme, e: MouseEvent<HTMLButtonElement>) => {
    if (id === theme) return;
    const r = e.currentTarget.getBoundingClientRect();
    withViewTransition("theme", () => applyTheme(id), { x: r.left + r.width / 2, y: r.top + r.height / 2 });
  };
  return (
    <div className="swatches" data-size={size} role="radiogroup" aria-label="Theme" data-testid="theme-swatches">
      {THEMES.map((t) => (
        <button
          key={t.id}
          type="button"
          role="radio"
          aria-checked={theme === t.id}
          className="swatch"
          data-swatch={t.id}
          title={`${t.label} — ${t.note}`}
          aria-label={t.label}
          onClick={(e) => pick(t.id, e)}
        >
          <span className="swatch-chip" aria-hidden="true">
            <span className="swatch-side" />
            <span className="swatch-dot" />
          </span>
          {size === "lg" && (
            <span className="swatch-text">
              <span className="swatch-name">{t.label}</span>
              <span className="swatch-note">{t.note}</span>
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
