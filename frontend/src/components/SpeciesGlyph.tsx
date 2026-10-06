/* Hand-drawn species glyphs (16px line art, 1.5px stroke) for specimen tags and case headers. */
import type { ReactElement, SVGProps } from "react";
import type { SpeciesCode } from "../api/cases";

type P = SVGProps<SVGSVGElement>;

const base = {
  width: 16,
  height: 16,
  viewBox: "0 0 16 16",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: false,
};

/** Cattle / buffalo: head with horns and ears. */
function Bov(props: P) {
  return (
    <svg {...base} {...props}>
      <path d="M3 4.2c.6 1.2 1.6 1.6 2.6 1.4M13 4.2c-.6 1.2-1.6 1.6-2.6 1.4" />
      <path d="M5.4 5.8h5.2l.6 4.2c.2 1.6-1 3-2.6 3h-1.2c-1.6 0-2.8-1.4-2.6-3z" />
      <path d="M5.4 7l-2.2.6M10.6 7l2.2.6M7 11.3h.01M9 11.3h.01" />
    </svg>
  );
}

/** Goat / sheep: head with swept horn and beard. */
function Cap(props: P) {
  return (
    <svg {...base} {...props}>
      <path d="M6 5.4c-.2-1.8.8-3 2.6-3.2M10 5.4c1.4-.6 2.6.2 2.8 1.8" />
      <path d="M5.6 5.6h4.8l-.4 4.6c-.1 1.2-1 2.1-2 2.1s-1.9-.9-2-2.1z" />
      <path d="M8 12.3v1.6M4.4 7l1.2.4M11.6 7l-1.2.4" />
    </svg>
  );
}

/** Poultry: hen in profile with comb. */
function Avi(props: P) {
  return (
    <svg {...base} {...props}>
      <path d="M5 4.2c.3-1 1.3-1.4 2-.8.4-.6 1.4-.4 1.4.4" />
      <path d="M5.2 5c-1.4.4-2 1.8-1.4 3.2.8 2 2.6 3.4 5 3.4 2.2 0 3.8-1.4 3.8-3.4 0-.8-.3-1.4-.8-1.9l-1.4.9C9 7.4 7.6 5.6 7.4 4.6" />
      <path d="M3.9 5.6l-1.4.5 1.3.6M7.2 11.6l-.4 2.2M9.4 11.6l.3 2.2" />
    </svg>
  );
}

/** Dog: head with drop ears. */
function Can(props: P) {
  return (
    <svg {...base} {...props}>
      <path d="M5.2 3.6c-1.4.2-2.2 1.6-2 3.4l1.4.4M10.8 3.6c1.4.2 2.2 1.6 2 3.4l-1.4.4" />
      <path d="M5.2 3.6h5.6l.4 5.6c.1 1.8-1.4 3.4-3.2 3.4S4.7 11 4.8 9.2z" />
      <path d="M7.2 10.4h1.6M6.6 7.2h.01M9.4 7.2h.01" />
    </svg>
  );
}

/** Cat: head with pointed ears and whiskers. */
function Fel(props: P) {
  return (
    <svg {...base} {...props}>
      <path d="M4.2 7.4V2.8l2.4 2.2h2.8l2.4-2.2v4.6" />
      <path d="M4.2 7.4c0 2.8 1.8 4.6 3.8 4.6s3.8-1.8 3.8-4.6" />
      <path d="M6.6 7.6h.01M9.4 7.6h.01M8 9.4v.6M2.4 9l2.2.2M2.6 10.6l2-.4M13.6 9l-2.2.2M13.4 10.6l-2-.4" />
    </svg>
  );
}

const GLYPH: Record<SpeciesCode, (p: P) => ReactElement> = { BOV: Bov, CAP: Cap, AVI: Avi, CAN: Can, FEL: Fel };

export function SpeciesGlyph({ code, ...props }: { code: SpeciesCode } & P) {
  const G = GLYPH[code];
  return <G {...props} />;
}
