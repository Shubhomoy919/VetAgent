import type { ReactNode } from "react";

/** Shared SVG filter defs, mounted once in the shell.
 *  #ink-rough: displaces edges with fractal noise and knocks out small speckles, like a rubber stamp. */
export function InkDefs() {
  return (
    <svg className="ink-defs" width="0" height="0" aria-hidden="true" focusable="false">
      <filter id="ink-rough" x="-6%" y="-14%" width="112%" height="128%" colorInterpolationFilters="sRGB">
        <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="3" result="warp" />
        <feDisplacementMap in="SourceGraphic" in2="warp" scale="2.4" xChannelSelector="R" yChannelSelector="G" result="edged" />
        <feTurbulence type="fractalNoise" baseFrequency="1.4" numOctaves="1" seed="11" result="grit" />
        <feColorMatrix in="grit" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.6 2.05" result="speckle" />
        <feComposite in="edged" in2="speckle" operator="in" />
      </filter>
    </svg>
  );
}

/** Hand-drawn underline: one slightly uneven riso-pink stroke that draws in. */
export function InkUnderline({ variant = 0 }: { variant?: number }) {
  const paths = [
    "M1 4.2C18 2.2 38 5 62 3.4S112 2 159 4.6",
    "M1 3.4C26 5 52 2.4 84 3.8S136 5.2 159 2.8",
    "M1 4.6C30 3 46 2.2 78 3.6S128 4.4 159 3.2",
  ];
  return (
    <svg className="ink-underline" viewBox="0 0 160 6" preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <path d={paths[variant % paths.length]} pathLength={1} />
    </svg>
  );
}

/** Section heading: numbered § (CSS counter), small caps, hand-drawn underline. */
export function SectionTitle({ children, id }: { children: ReactNode; id?: string }) {
  const text = typeof children === "string" ? children : "";
  return (
    <h2 className="sc-h2" id={id}>
      <span className="sc-h2-text">{children}</span>
      <InkUnderline variant={text.length} />
    </h2>
  );
}
