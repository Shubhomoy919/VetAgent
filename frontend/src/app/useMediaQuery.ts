import { useSyncExternalStore } from "react";

/** Subscribe to a CSS media query. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}

/** Layout breakpoints from the spec: three panes ≥ 1440, case drawer 1024–1439, condition tabs < 1024. */
export const WIDE = "(min-width: 1440px)";
export const NARROW = "(max-width: 1023px)";
