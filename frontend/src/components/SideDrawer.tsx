import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, type ReactNode } from "react";
import "./drawer.css";

const EASE = [0.2, 0.8, 0.2, 1] as const;

interface Props {
  open: boolean;
  title: ReactNode;
  eyebrow?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
  testId?: string;
}

/** Right-hand drawer with scrim, Esc to close and focus moved inside on open. */
export function SideDrawer({ open, title, eyebrow, onClose, children, footer, wide, testId }: Props) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const t = window.setTimeout(() => {
      ref.current?.querySelector<HTMLElement>("input, select, textarea, button")?.focus();
    }, 30);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("keydown", onKey);
      prev?.focus?.();
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="drawer-scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16 }}
            onClick={onClose}
          />
          <motion.aside
            ref={ref}
            className="drawer"
            data-wide={wide}
            role="dialog"
            aria-modal="true"
            aria-labelledby="side-drawer-title"
            initial={{ x: 24, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 24, opacity: 0 }}
            transition={{ duration: 0.22, ease: EASE }}
            data-testid={testId}
          >
            <header className="drawer-head">
              <div>
                {eyebrow && <span className="eyebrow">{eyebrow}</span>}
                <h2 id="side-drawer-title" className="serif drawer-title">
                  {title}
                </h2>
              </div>
              <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
                ×
              </button>
            </header>
            <div className="drawer-body">{children}</div>
            {footer && <footer className="drawer-foot">{footer}</footer>}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
