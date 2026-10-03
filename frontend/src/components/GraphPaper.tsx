import { useId } from "react";

/** Faint graph-paper grid (8px minor, 40px major) drawn as an SVG pattern. */
export function GraphPaper() {
  const id = useId().replace(/:/g, "");
  return (
    <svg className="graph-paper" aria-hidden="true" focusable="false">
      <defs>
        <pattern id={`${id}-minor`} width="8" height="8" patternUnits="userSpaceOnUse">
          <path d="M8 0H0V8" fill="none" style={{ stroke: "var(--grid-line)" }} strokeWidth="1" />
        </pattern>
        <pattern id={`${id}-major`} width="40" height="40" patternUnits="userSpaceOnUse">
          <rect width="40" height="40" fill={`url(#${id}-minor)`} />
          <path d="M40 0H0V40" fill="none" style={{ stroke: "var(--grid-major)" }} strokeWidth="1" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${id}-major)`} />
    </svg>
  );
}
