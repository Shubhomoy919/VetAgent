import { useEffect, useState } from "react";
import "./PrintMarks.css";

const INKS = ["pink", "sunflower", "orange", "cornflower", "violet", "mint", "madder"] as const;
const SESSION_KEY = "vab.colorbar.printed";

/** Registration target (circle + cross) as printed on press sheets. */
function Target() {
  return (
    <svg className="cb-target" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
      <circle cx="6" cy="6" r="3" />
      <path d="M6 0v12M0 6h12" />
    </svg>
  );
}

/** The printer's colour bar under the top bar: every ink at 100 / 55 / 25%, registration targets and
 *  an ink check. On the first load of a session it prints left to right in one printer-head pass. */
export function ColorBar() {
  const [firstPass] = useState(() => {
    try {
      if (sessionStorage.getItem(SESSION_KEY)) return false;
      sessionStorage.setItem(SESSION_KEY, "1");
      return true;
    } catch {
      return false;
    }
  });
  return (
    <div className="colorbar" data-first-pass={firstPass || undefined} aria-hidden="true" data-testid="colorbar">
      <Target />
      <span className="cb-swatches">
        {INKS.map((ink) => (
          <span key={ink} className="cb-ink" data-ink={ink}>
            <span className="cb-sq" data-tint="100" />
            <span className="cb-sq" data-tint="55" />
            <span className="cb-sq" data-tint="25" />
          </span>
        ))}
      </span>
      <Target />
      <span className="cb-check mono">
        ink check {INKS.length} / {INKS.length}
      </span>
    </div>
  );
}

/** Crop marks at the four corners of the content area; both strokes draw once on first load. */
export function CropMarks() {
  const [drawn, setDrawn] = useState(false);
  useEffect(() => {
    const t = window.requestAnimationFrame(() => setDrawn(true));
    return () => window.cancelAnimationFrame(t);
  }, []);
  return (
    <div className="cropmarks" data-drawn={drawn || undefined} aria-hidden="true">
      {(["tl", "tr", "bl", "br"] as const).map((c) => (
        <svg key={c} className="crop" data-corner={c} viewBox="0 0 18 18" focusable="false">
          <path d="M0 9h12" pathLength={1} />
          <path d="M9 0v12" pathLength={1} />
        </svg>
      ))}
    </div>
  );
}
