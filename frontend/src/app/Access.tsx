/* Access-code prompt (inline and as a dialog), read-only notes, and the gate for Review and Settings. */
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useId, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { UnlockError, useAuth, useAuthActions } from "../api/auth";
import { PageTitle } from "../components/PageHeader";
import { AccessDialogContext, useAccessDialog } from "./accessDialog";
import "./access.css";

const EASE = [0.2, 0.8, 0.2, 1] as const;

function minutes(s: number): string {
  const m = Math.max(1, Math.ceil(s / 60));
  return `${m} min`;
}

/** The code form. Calls onDone after a successful unlock. */
export function AccessCodeForm({ onDone, autoFocus = false }: { onDone?: () => void; autoFocus?: boolean }) {
  const id = useId();
  const { data: auth } = useAuth();
  const { unlock } = useAuthActions();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  if (auth && !auth.unlock_available) {
    return (
      <p className="access-note" role="status">
        This deployment is read-only. Runs, edits, Review and Settings are turned off.
      </p>
    );
  }

  const lockedFor = auth?.locked_for_s ?? 0;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await unlock(code);
      setCode("");
      onDone?.();
    } catch (err) {
      setError(err instanceof UnlockError ? err.message : err instanceof Error ? err.message : "Could not unlock");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="access-form" onSubmit={(e) => void submit(e)} data-testid="access-form">
      <label htmlFor={id} className="ff-label">
        Access code
      </label>
      <div className="access-row">
        <input
          ref={inputRef}
          id={id}
          name="access-code"
          type="password"
          autoComplete="current-password"
          className="ff-input mono"
          value={code}
          maxLength={256}
          onChange={(e) => setCode(e.target.value)}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-err` : `${id}-hint`}
          disabled={busy || lockedFor > 0}
        />
        <button type="submit" className="btn btn-primary" disabled={busy || !code.trim() || lockedFor > 0}>
          {busy ? "Checking…" : "Unlock"}
        </button>
      </div>
      {error ? (
        <span id={`${id}-err`} className="ff-error" role="alert">
          {error}
        </span>
      ) : lockedFor > 0 ? (
        <span id={`${id}-hint`} className="ff-error" role="alert">
          Too many wrong codes. Try again in {minutes(lockedFor)}.
        </span>
      ) : (
        <span id={`${id}-hint`} className="ff-hint">
          Ask the study team for the code. The session lasts until you lock it or it expires.
        </span>
      )}
    </form>
  );
}

// ---------- dialog ----------

export function AccessDialogProvider({ children }: { children: ReactNode }) {
  const [isOpen, setOpen] = useState(false);
  const prevFocus = useRef<HTMLElement | null>(null);
  // Remember what had focus before the dialog's input takes it, so closing returns focus there.
  const open = useCallback(() => {
    prevFocus.current = document.activeElement as HTMLElement | null;
    setOpen(true);
  }, []);
  const value = useMemo(() => ({ open }), [open]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("keydown", onKey, true);
      prevFocus.current?.focus?.();
    };
  }, [isOpen]);

  return (
    <AccessDialogContext.Provider value={value}>
      {children}
      <AnimatePresence>
        {isOpen && (
          <div className="access-layer">
            <motion.div className="access-scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }} onClick={() => setOpen(false)} />
            <motion.div
              className="access-dialog"
              role="dialog"
              aria-modal="true"
              aria-labelledby="access-title"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              transition={{ duration: 0.16, ease: EASE }}
            >
              <div className="access-head">
                <h2 id="access-title" className="serif access-title">
                  Unlock runs and editing
                </h2>
                <button type="button" className="icon-button" onClick={() => setOpen(false)} aria-label="Close">
                  ×
                </button>
              </div>
              <p className="access-body">
                Anyone can browse the published results. Running cases, editing data, Review and Settings need the study's access code.
              </p>
              <AccessCodeForm autoFocus onDone={() => setOpen(false)} />
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </AccessDialogContext.Provider>
  );
}

// ---------- inline pieces ----------

/** A one-line read-only notice with an Unlock button, for toolbars and page headers. */
export function ReadOnlyNote({ what }: { what: string }) {
  const { data: auth } = useAuth();
  const { open } = useAccessDialog();
  return (
    <div className="readonly-note" role="note" data-testid="readonly-note">
      <span>
        Read-only. {auth?.unlock_available === false ? `${what} is turned off on this deployment.` : `Enter the access code to ${what.toLowerCase()}.`}
      </span>
      {auth?.unlock_available !== false && (
        <button type="button" className="btn" onClick={open}>
          Enter access code
        </button>
      )}
    </div>
  );
}

/** Whole-page gate: shows the page to admins, the code prompt to everyone else. */
export function AccessGate({ title, plate, purpose, children }: { title: string; plate: string; purpose: string; children: ReactNode }) {
  const { data: auth, isPending, error } = useAuth();
  if (isPending) return <p className="empty-body access-gate">Checking access…</p>;
  if (error) {
    return (
      <p className="error-text access-gate" role="alert">
        {error.message}
      </p>
    );
  }
  if (auth.admin) return <>{children}</>;
  return (
    <div className="datapage">
      <header className="dp-header">
        <div>
          <PageTitle plate={plate}>{title}</PageTitle>
        </div>
      </header>
      <section className="access-gate" aria-labelledby="gate-title" data-testid="access-gate">
        <h2 id="gate-title" className="serif access-title">
          {title} needs the access code
        </h2>
        <p className="access-body">{purpose}</p>
        <AccessCodeForm autoFocus />
      </section>
    </div>
  );
}
