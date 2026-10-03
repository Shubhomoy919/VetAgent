import type { ComponentType, SVGProps } from "react";
import { BenchIcon } from "../components/icons";

export interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
}

export interface NavGroup {
  label: "WORK" | "DATA" | "RESULTS" | "ABOUT";
  items: NavItem[];
}

/**
 * Sidebar navigation. A page is listed here only once it is fully built
 * (project rule). Groups with no items are not rendered.
 */
export const NAV: NavGroup[] = [
  { label: "WORK", items: [{ to: "/", label: "Bench", icon: BenchIcon }] },
  { label: "DATA", items: [] },
  { label: "RESULTS", items: [] },
  { label: "ABOUT", items: [] },
];
