import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";
export type ThemePref = Theme | "system";
export type Density = "comfortable" | "compact";

const KEY = "vab.theme";
const DENSITY_KEY = "vab.density";
const EVENT = "vab-appearance";

function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function store(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Storage unavailable (private mode): the change still applies for this session.
  }
}

export function readThemePref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

/** Apply a theme preference; "system" follows the OS setting and clears the stored choice. */
export function applyThemePref(pref: ThemePref): void {
  const theme = pref === "system" ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : pref;
  document.documentElement.dataset.theme = theme;
  store(KEY, pref === "system" ? null : pref);
  window.dispatchEvent(new Event(EVENT));
}

export function readDensity(): Density {
  return document.documentElement.dataset.density === "compact" ? "compact" : "comfortable";
}

export function applyDensity(d: Density): void {
  document.documentElement.dataset.density = d;
  store(DENSITY_KEY, d === "compact" ? d : null);
  window.dispatchEvent(new Event(EVENT));
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(currentTheme);

  useEffect(() => {
    const sync = () => setThemeState(currentTheme());
    window.addEventListener(EVENT, sync);
    return () => window.removeEventListener(EVENT, sync);
  }, []);

  const setTheme = useCallback((next: Theme) => applyThemePref(next), []);
  const toggle = useCallback(() => applyThemePref(currentTheme() === "dark" ? "light" : "dark"), []);

  return { theme, setTheme, toggle };
}

export function usePersistentFlag(key: string, initial: () => boolean) {
  const [value, setValue] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem(key);
      if (stored === "1" || stored === "0") return stored === "1";
    } catch {
      // fall through to the computed default
    }
    return initial();
  });

  const update = useCallback(
    (next: boolean) => {
      setValue(next);
      store(key, next ? "1" : "0");
    },
    [key],
  );

  return [value, update] as const;
}
