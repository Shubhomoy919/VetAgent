import type { ComponentType, SVGProps } from "react";
import {
  BenchIcon,
  CasesIcon,
  DrugIcon,
  OverviewIcon,
  ReviewIcon,
  RunsIcon,
  ScorecardIcon,
  SettingsIcon,
  StudyIcon,
} from "../components/icons";

export interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
}

export interface NavGroup {
  label: "Work" | "Data" | "Results" | "About";
  items: NavItem[];
}

/**
 * Sidebar navigation. A page is listed here only once it is fully built
 * (project rule). Groups with no items are not rendered.
 */
export const NAV: NavGroup[] = [
  {
    label: "Work",
    items: [
      { to: "/", label: "Bench", icon: BenchIcon },
      { to: "/runs", label: "Runs", icon: RunsIcon },
      { to: "/review", label: "Review", icon: ReviewIcon },
    ],
  },
  {
    label: "Data",
    items: [
      { to: "/cases", label: "Cases", icon: CasesIcon },
      { to: "/drugs", label: "Drug table", icon: DrugIcon },
    ],
  },
  { label: "Results", items: [{ to: "/scorecard", label: "Scorecard", icon: ScorecardIcon }] },
  {
    label: "About",
    items: [
      { to: "/study", label: "Study design", icon: StudyIcon },
      { to: "/overview", label: "Overview", icon: OverviewIcon },
      { to: "/settings", label: "Settings", icon: SettingsIcon },
    ],
  },
];
