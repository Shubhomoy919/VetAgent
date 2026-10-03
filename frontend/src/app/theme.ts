import { useCallback, useState } from "react";

export type Theme = "light" | "dark";

const KEY = "vab.theme";

function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(currentTheme);

  const setTheme = useCallback((next: Theme) => {
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // Storage unavailable (private mode): theme still applies for this session.
    }
    setThemeState(next);
  }, []);

  const toggle = useCallback(() => setTheme(currentTheme() === "dark" ? "light" : "dark"), [setTheme]);

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
      try {
        localStorage.setItem(key, next ? "1" : "0");
      } catch {
        // ignore
      }
    },
    [key],
  );

  return [value, update] as const;
}
