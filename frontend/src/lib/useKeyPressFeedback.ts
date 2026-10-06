import { useEffect } from "react";

/** 9. Keyboard caps: when a shortcut key is pressed, every visible <kbd> showing that key
 *  presses down briefly, so the on-screen key confirms the keystroke. */
export function useKeyPressFeedback(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.repeat) return;
      const key = e.key.length === 1 ? e.key.toLowerCase() : e.key.toLowerCase();
      const label = e.ctrlKey && key === "k" ? "ctrl k" : key;
      for (const kbd of document.querySelectorAll<HTMLElement>("kbd")) {
        if (kbd.textContent?.trim().toLowerCase() !== label) continue;
        kbd.classList.add("is-pressed");
        window.setTimeout(() => kbd.classList.remove("is-pressed"), 140);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
