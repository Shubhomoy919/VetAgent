import { flushSync } from "react-dom";

export type VtKind = "route" | "case" | "theme";

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** True when the View Transitions API can be used (and the user has not asked for reduced motion). */
export function canViewTransition(): boolean {
  return typeof document !== "undefined" && "startViewTransition" in document && !reducedMotion();
}

/** Mark the next transition's kind on <html> so motion.css animates only the matching region. */
export function markTransition(kind: VtKind): void {
  if (!canViewTransition()) return;
  document.documentElement.dataset.vt = kind;
  window.setTimeout(() => {
    if (document.documentElement.dataset.vt === kind) delete document.documentElement.dataset.vt;
  }, 600);
}

/** Run a React state update inside a view transition (falls back to a plain update). */
export function withViewTransition(kind: VtKind, update: () => void, origin?: { x: number; y: number }): void {
  if (!canViewTransition()) {
    update();
    return;
  }
  const root = document.documentElement;
  root.dataset.vt = kind;
  if (origin) {
    root.style.setProperty("--vt-x", `${origin.x}px`);
    root.style.setProperty("--vt-y", `${origin.y}px`);
    const r = Math.hypot(Math.max(origin.x, window.innerWidth - origin.x), Math.max(origin.y, window.innerHeight - origin.y));
    root.style.setProperty("--vt-r", `${Math.ceil(r)}px`);
  }
  const t = document.startViewTransition(() => flushSync(update));
  void t.finished.finally(() => {
    if (root.dataset.vt === kind) delete root.dataset.vt;
  });
}
