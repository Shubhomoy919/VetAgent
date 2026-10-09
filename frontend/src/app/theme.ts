import { useCallback, useState } from "react";

function store(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Storage unavailable (private mode): the change still applies for this session.
  }
}

/** A boolean UI preference remembered in localStorage (e.g. the collapsed sidebar). */
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
