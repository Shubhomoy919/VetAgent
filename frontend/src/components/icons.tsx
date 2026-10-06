/* Hand-drawn 16px line icons. 1.25px strokes to match the hairline system. */
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Svg(props: IconProps) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    />
  );
}

/** Lab bench: worktop with a flask. */
export function BenchIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M1.5 12.5h13M3 12.5v2M13 12.5v2" />
      <path d="M6.5 3h3M7 3v3.2L4.6 10.6a.6.6 0 0 0 .5.9h5.8a.6.6 0 0 0 .5-.9L9 6.2V3" />
    </Svg>
  );
}

/** Scorecard: two dot-and-whisker rows. */
export function ScorecardIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M2 4.5h12M2 11.5h12" strokeOpacity="0.35" />
      <path d="M4 4.5h6M6.5 11.5h6" />
      <circle cx="7" cy="4.5" r="1.6" fill="currentColor" />
      <circle cx="9.5" cy="11.5" r="1.6" fill="currentColor" />
    </Svg>
  );
}

/** Cases: a luggage tag. */
export function CasesIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M5.5 2.5h8v11h-8L2.5 8z" />
      <circle cx="6.2" cy="8" r="1" />
      <path d="M8.5 6h3M8.5 10h3" />
    </Svg>
  );
}

/** Drug table: a capsule. */
export function DrugIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="1.8" y="5.2" width="12.4" height="5.6" rx="2.8" transform="rotate(-35 8 8)" />
      <path d="M6.3 5.6l3.3 4.8" />
    </Svg>
  );
}

/** Runs: stacked log entries. */
export function RunsIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M2.5 3.5h11M2.5 8h11M2.5 12.5h7" />
      <circle cx="12.5" cy="12.5" r="1.3" />
    </Svg>
  );
}

/** Review: a clipboard with a check. */
export function ReviewIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="3" y="2.5" width="10" height="11.5" rx="1.2" />
      <path d="M6 2.5v1.5h4V2.5M5.8 9l1.7 1.7 3-3.4" />
    </Svg>
  );
}

/** Study design: the ablation ladder. */
export function StudyIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 2v12M12 2v12M4 5h8M4 8h8M4 11h8" />
    </Svg>
  );
}

/** Overview: a one-page document. */
export function OverviewIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 1.8h5.5L12.5 5v9.2H4z" />
      <path d="M9.5 1.8V5h3M6 8h4.5M6 10.5h4.5" />
    </Svg>
  );
}

/** Settings: two sliders. */
export function SettingsIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M2.5 5h11M2.5 11h11" />
      <circle cx="6" cy="5" r="1.7" fill="var(--surface)" />
      <circle cx="10.5" cy="11" r="1.7" fill="var(--surface)" />
    </Svg>
  );
}

export function SunIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="8" cy="8" r="2.75" />
      <path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" />
    </Svg>
  );
}

export function MoonIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M13.2 9.6A5.5 5.5 0 0 1 6.4 2.8a5.5 5.5 0 1 0 6.8 6.8Z" />
    </Svg>
  );
}

export function CollapseIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="1.75" y="2.25" width="12.5" height="11.5" rx="1.5" />
      <path d="M5.75 2.25v11.5M10.5 6l-2 2 2 2" />
    </Svg>
  );
}

export function ExpandIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="1.75" y="2.25" width="12.5" height="11.5" rx="1.5" />
      <path d="M5.75 2.25v11.5M8.5 6l2 2-2 2" />
    </Svg>
  );
}
