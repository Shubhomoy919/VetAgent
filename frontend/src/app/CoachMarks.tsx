import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router";
import "./coach.css";

const KEY = "vab.coach";
const EASE = [0.2, 0.8, 0.2, 1] as const;

const STEPS: { target: string; title: string; body: string; keys: string[] }[] = [
  { target: "cases", title: "Choose a specimen", body: "The ledger lists every case as a tagged specimen. J and K move; X ticks a case for a batch run.", keys: ["J", "K", "X"] },
  { target: "runbar", title: "Examine it five ways", body: "R runs the specimen through C0–C4. The meter lights one segment per result; LEDs show each condition.", keys: ["R"] },
  { target: "deck", title: "Read the instruments", body: "Each card carries a vital-signs trace, the triage strip, the dose dial and the verdict stamps. 1–5 jump between conditions.", keys: ["1", "5"] },
  { target: "palette", title: "Everything else", body: "Ctrl K opens the command palette; ? lists every shortcut.", keys: ["Ctrl K", "?"] },
];

function seen(): boolean {
  try {
    return localStorage.getItem(KEY) === "done";
  } catch {
    return true;
  }
}

/** First-run coach marks on the Bench: four steps, non-blocking, dismissible, remembered. */
export function CoachMarks() {
  const { pathname } = useLocation();
  const [step, setStep] = useState<number | null>(() => (seen() ? null : 0));
  const active = pathname === "/" && step !== null;

  const finish = () => {
    setStep(null);
    try {
      localStorage.setItem(KEY, "done");
    } catch {
      // storage unavailable: dismissed for this session only
    }
  };

  // Outline the element the current step talks about (CSS keyed off <html data-coach-step>,
  // so it applies whenever the target is on screen, including after lazy content loads).
  useEffect(() => {
    if (!active || step === null) return;
    const root = document.documentElement;
    root.dataset.coachStep = STEPS[step]?.target ?? "";
    return () => {
      delete root.dataset.coachStep;
    };
  }, [active, step]);

  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") finish();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active]);

  const s = step === null ? undefined : STEPS[step];
  return (
    <AnimatePresence>
      {active && s && step !== null && (
        <motion.aside
          key="coach"
          className="coach paper-slip"
          role="dialog"
          aria-label={`Field manual, step ${step + 1} of ${STEPS.length}`}
          data-testid="coach"
          initial={{ opacity: 0, y: 10, rotate: -1.5 }}
          animate={{ opacity: 1, y: 0, rotate: -0.8 }}
          exit={{ opacity: 0, y: 6 }}
          transition={{ duration: 0.22, ease: EASE }}
        >
          <div className="coach-head">
            <span className="coach-step mono">
              Field manual · {String(step + 1).padStart(2, "0")} / {String(STEPS.length).padStart(2, "0")}
            </span>
            <button type="button" className="coach-skip" onClick={finish}>
              Skip
            </button>
          </div>
          <motion.div key={step} initial={{ opacity: 0, x: 6 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.18, ease: EASE }}>
            <p className="coach-title serif">{s.title}</p>
            <p className="coach-body">{s.body}</p>
            <p className="coach-keys">
              {s.keys.map((k) => (
                <kbd key={k}>{k}</kbd>
              ))}
            </p>
          </motion.div>
          <div className="coach-foot">
            <span className="coach-pips" aria-hidden="true">
              {STEPS.map((_, i) => (
                <span key={i} className="led" data-state={i < step ? "done" : i === step ? "queued" : undefined} />
              ))}
            </span>
            {step > 0 && (
              <button type="button" className="btn" onClick={() => setStep(step - 1)}>
                Back
              </button>
            )}
            <button type="button" className="btn btn-primary" onClick={() => (step + 1 < STEPS.length ? setStep(step + 1) : finish())}>
              {step + 1 < STEPS.length ? "Next" : "Done"}
            </button>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
