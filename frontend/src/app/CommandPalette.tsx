/* Ctrl+K / ⌘K command palette: pages, cases, actions. Also hosts the "?" shortcuts sheet. */
import { Command } from "cmdk";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { useCases } from "../api/cases";
import { NAV } from "./nav";
import { SHORTCUTS } from "./shortcuts";
import { applyDensity, applyThemePref, readDensity } from "./theme";
import "./palette.css";

const EASE = [0.2, 0.8, 0.2, 1] as const;

function isTypingTarget(el: EventTarget | null): boolean {
  return el instanceof HTMLElement && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

function Modal({ open, onClose, label, children, wide }: { open: boolean; onClose: () => void; label: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const t = window.setTimeout(() => ref.current?.querySelector<HTMLElement>("input, button")?.focus(), 20);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("keydown", onKey, true);
      prev?.focus?.();
    };
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <div className="pal-layer">
          <motion.div className="pal-scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }} onClick={onClose} />
          <motion.div
            ref={ref}
            className="pal"
            data-wide={wide}
            role="dialog"
            aria-modal="true"
            aria-label={label}
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.16, ease: EASE }}
          >
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [help, setHelp] = useState(false);
  const navigate = useNavigate();
  const { data: cases } = useCases();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setHelp(false);
        setOpen((o) => !o);
      } else if (e.key === "?" && !isTypingTarget(e.target) && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        setOpen(false);
        setHelp((h) => !h);
      }
    };
    const onOpen = () => {
      setHelp(false);
      setOpen(true);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("vab:palette", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("vab:palette", onOpen);
    };
  }, []);

  const go = (to: string) => {
    setOpen(false);
    navigate(to);
  };

  return (
    <>
      <Modal open={open} onClose={() => setOpen(false)} label="Command palette">
        <Command label="Command palette" className="cmdk" loop>
          <Command.Input className="cmdk-input" placeholder="Go to a page, open a case, or run an action…" />
          <Command.List className="cmdk-list">
            <Command.Empty className="cmdk-empty">No match.</Command.Empty>
            <Command.Group heading="Pages" className="cmdk-group">
              {NAV.flatMap((g) => g.items).map(({ to, label, icon: Icon }) => (
                <Command.Item key={to} value={`page ${label}`} onSelect={() => go(to)} className="cmdk-item">
                  <Icon className="cmdk-icon" />
                  {label}
                </Command.Item>
              ))}
            </Command.Group>
            <Command.Group heading="Actions" className="cmdk-group">
              <Command.Item value="action toggle theme dark light" className="cmdk-item"
                onSelect={() => { applyThemePref(document.documentElement.dataset.theme === "dark" ? "light" : "dark"); setOpen(false); }}>
                Toggle light / dark theme
              </Command.Item>
              <Command.Item value="action toggle density compact comfortable" className="cmdk-item"
                onSelect={() => { applyDensity(readDensity() === "compact" ? "comfortable" : "compact"); setOpen(false); }}>
                Toggle compact density
              </Command.Item>
              <Command.Item value="action keyboard shortcuts help" className="cmdk-item" onSelect={() => { setOpen(false); setHelp(true); }}>
                Keyboard shortcuts <kbd className="cmdk-kbd">?</kbd>
              </Command.Item>
            </Command.Group>
            <Command.Group heading="Cases" className="cmdk-group">
              {(cases ?? []).map((c) => (
                <Command.Item key={c.case_id} value={`case ${c.case_id} ${c.species} ${c.signalment.breed} ${c.question_type}`}
                  onSelect={() => go(`/?case=${encodeURIComponent(c.case_id)}`)} className="cmdk-item">
                  <span className="mono cmdk-case">{c.case_id}</span>
                  <span className="cmdk-sub">{c.species} · {c.signalment.breed}</span>
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
        </Command>
      </Modal>

      <Modal open={help} onClose={() => setHelp(false)} label="Keyboard shortcuts" wide>
        <div className="help" data-testid="shortcuts-help">
          <div className="help-head">
            <h2 className="serif help-title">Keyboard shortcuts</h2>
            <button type="button" className="icon-button" onClick={() => setHelp(false)} aria-label="Close">×</button>
          </div>
          <div className="help-grid">
            {SHORTCUTS.map((g) => (
              <section key={g.group}>
                <h3 className="eyebrow">{g.group}</h3>
                <dl>
                  {g.items.map(([k, v]) => (
                    <div key={k + v} className="help-row">
                      <dt><kbd className="cmdk-kbd">{k}</kbd></dt>
                      <dd>{v}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ))}
          </div>
        </div>
      </Modal>
    </>
  );
}
