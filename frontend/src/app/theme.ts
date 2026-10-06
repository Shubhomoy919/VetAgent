import { useCallback, useEffect, useState } from "react";

export type Theme = "riso-black" | "cyanotype" | "kalamkari";
export type Density = "comfortable" | "compact";

export const THEMES: { id: Theme; label: string; note: string }[] = [
  { id: "riso-black", label: "Riso Black", note: "Pure black, risograph inks (default)" },
  { id: "cyanotype", label: "Cyanotype", note: "Prussian-blue print, cyan line work" },
  { id: "kalamkari", label: "Kalamkari", note: "Warm Indian textile pigments" },
];
export const DEFAULT_THEME: Theme = "riso-black";

const KEY = "vab.theme";
const DENSITY_KEY = "vab.density";
const EVENT = "vab-appearance";

/** Earlier builds stored "light" / "dark" / "bone-block"; anything unknown falls back to Riso Black. */
export function normaliseTheme(v: string | null | undefined): Theme {
  if (v === "riso-black" || v === "cyanotype" || v === "kalamkari") return v;
  return DEFAULT_THEME;
}

function currentTheme(): Theme {
  return normaliseTheme(document.documentElement.dataset.theme);
}

function store(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Storage unavailable (private mode): the change still applies for this session.
  }
}

export function readTheme(): Theme {
  try {
    return normaliseTheme(localStorage.getItem(KEY));
  } catch {
    return DEFAULT_THEME;
  }
}

/** Apply and remember a theme. */
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  store(KEY, theme);
  window.dispatchEvent(new Event(EVENT));
}

const LEDGER_KEY = "vab.ledger";

export function readLedgerDense(): boolean {
  return document.documentElement.dataset.ledger === "dense";
}

/** Ledger density (dense / comfortable) for all ledger tables; remembered per browser. */
export function applyLedgerDense(dense: boolean): void {
  document.documentElement.dataset.ledger = dense ? "dense" : "comfortable";
  store(LEDGER_KEY, dense ? "dense" : null);
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

  const setTheme = useCallback((next: Theme) => applyTheme(next), []);
  return { theme, setTheme };
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
