/* "?" opens the keyboard-shortcut help overlay (Esc closes it). */
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { SHORTCUTS } from "./shortcuts";
import "./help.css";

function isTypingTarget(el: EventTarget | null): boolean {
  return el instanceof HTMLElement && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

export function ShortcutHelp() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "?" && !isTypingTarget(e.target) && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const t = window.setTimeout(() => ref.current?.querySelector<HTMLElement>("button")?.focus(), 20);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("keydown", onKey, true);
      prev?.focus?.();
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <div className="hl-layer">
          <motion.div className="hl-scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }} onClick={() => setOpen(false)} />
          <motion.div
            ref={ref}
            className="hl"
            role="dialog"
            aria-modal="true"
            aria-label="Keyboard shortcuts"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
          >
            <div className="help" data-testid="shortcuts-help">
              <div className="help-head">
                <h2 className="serif help-title">Keyboard shortcuts</h2>
                <button type="button" className="icon-button" onClick={() => setOpen(false)} aria-label="Close">
                  ×
                </button>
              </div>
              <div className="help-grid">
                {SHORTCUTS.map((g) => (
                  <section key={g.group}>
                    <h3 className="eyebrow">{g.group}</h3>
                    <dl>
                      {g.items.map(([k, v]) => (
                        <div key={k + v} className="help-row">
                          <dt>
                            <kbd className="hl-kbd">{k}</kbd>
                          </dt>
                          <dd>{v}</dd>
                        </div>
                      ))}
                    </dl>
                  </section>
                ))}
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
