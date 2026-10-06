import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { formatAge, formatSex, type Case } from "../../api/cases";
import { SpecimenTag, TypePill, UnverifiedTag } from "../../components/Tags";

const EASE = [0.2, 0.8, 0.2, 1] as const;

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="sig-field">
      <dt className="eyebrow">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function yesNo(v: boolean | null): string {
  return v === null ? "not stated" : v ? "yes" : "no";
}

export function GoldPanel({ c, onCite }: { c: Case; onCite?: (page: number) => void }) {
  const g = c.gold_answer;
  return (
    <motion.div
      className="gold"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.24, ease: EASE }}
      data-testid="gold-answer"
    >
      <dl className="gold-grid">
        <Field label="Most likely">
          <span className="gold-dx">{g.most_likely}</span>
        </Field>
        <Field label="Triage">
          <span className="mono" data-triage={g.triage}>
            {g.triage}
          </span>
        </Field>
        {g.drug && (
          <Field label="Drug">
            {g.drug} — <span className="mono" data-drug-status={g.drug_status}>{g.drug_status}</span>
          </Field>
        )}
        {g.dose_mg && (
          <Field label="Dose">
            <span className="mono">
              {g.dose_mg.min === g.dose_mg.max ? g.dose_mg.min : `${g.dose_mg.min}–${g.dose_mg.max}`} mg
            </span>
          </Field>
        )}
        {g.withdrawal_known !== null && (
          <Field label="Withdrawal">
            <span className="mono">
              {g.withdrawal_known ? `${g.withdrawal_days} days` : "not stated in source — check label"}
            </span>
          </Field>
        )}
        <Field label="Escalate">{yesNo(g.escalate)}</Field>
        <Field label="Zoonosis">{yesNo(g.zoonosis_warning)}</Field>
        <Field label="Notifiable">{yesNo(g.notifiable)}</Field>
      </dl>
      {g.differentials.length > 0 && (
        <p className="gold-diff">
          <span className="eyebrow">Differentials </span>
          {g.differentials.join(" · ")}
        </p>
      )}
      <ul className="gold-points">
        {g.key_points.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ul>
      <div className="gold-sources">
        {g.citations.map((cit) =>
          onCite && cit.page !== null ? (
            <button
              type="button"
              className="cite-chip mono"
              key={`${cit.source}-${cit.page}`}
              title={cit.source}
              onClick={() => onCite(cit.page as number)}
            >
              SVTG p.{cit.page}
            </button>
          ) : (
            <span className="cite-chip mono" key={`${cit.source}-${cit.page}`} title={cit.source}>
              SVTG p.{cit.page}
            </span>
          ),
        )}
        <span className="gold-source-text">{c.source}</span>
      </div>
    </motion.div>
  );
}

export function CaseDetail({ c, onOpenDossier }: { c: Case; onOpenDossier?: () => void }) {
  const [revealed, setRevealed] = useState(false);
  const s = c.signalment;

  // G toggles the gold answer.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target;
      const typing = el instanceof HTMLElement && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
      if (typing || e.ctrlKey || e.metaKey || e.altKey || e.key.toLowerCase() !== "g") return;
      e.preventDefault();
      setRevealed((r) => !r);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <article className="case-detail" aria-labelledby="case-detail-id" data-testid="case-detail">
      <header className="case-detail-head">
        <div className="case-head-tags">
          <SpecimenTag caseId={c.case_id} size="lg" />
          <TypePill type={c.question_type} />
          {!c.vet_verified && <UnverifiedTag />}
          {onOpenDossier && (
            <button type="button" className="btn case-dossier-btn" onClick={onOpenDossier} data-testid="open-dossier">
              Dossier
            </button>
          )}
        </div>
        <h3 id="case-detail-id" className="case-title serif misreg">
          <span className="visually-hidden">Case {c.case_id}: </span>
          {s.breed}
        </h3>
      </header>

      <dl className="sig-strip" aria-label="Signalment">
        <Field label="Species">
          <span data-testid="case-species">{c.species}</span>
        </Field>
        <Field label="Age">
          <span className="mono">{formatAge(s.age_months)}</span>
        </Field>
        <Field label="Sex">
          {formatSex(s.sex)}
          {s.sex === "female" && s.lactating && <span className="sig-sub"> · lactating</span>}
        </Field>
        <Field label="Weight">
          <span className="mono">{s.weight_kg} kg</span>
        </Field>
      </dl>

      <section className="case-block">
        <h4 className="eyebrow">History</h4>
        <p>{c.history}</p>
      </section>

      <section className="case-block">
        <h4 className="eyebrow">Owner narrative</h4>
        <blockquote className="narrative">{c.owner_narrative}</blockquote>
      </section>

      <section className="case-block">
        <h4 className="eyebrow">Clinical signs</h4>
        <ul className="sign-tags">
          {c.clinical_signs.map((sign) => (
            <li key={sign}>{sign}</li>
          ))}
        </ul>
      </section>

      {c.red_flags.length > 0 && (
        <section className="case-block">
          <h4 className="eyebrow red-flag-label">Red flags</h4>
          <ul className="sign-tags red-flags">
            {c.red_flags.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="case-block question">
        <h4 className="eyebrow">Question</h4>
        <p className="question-text">{c.question}</p>
      </section>

      <section className="case-block">
        <button
          type="button"
          className="reveal-button"
          aria-expanded={revealed}
          onClick={() => setRevealed(!revealed)}
          data-testid="reveal-gold"
        >
          {revealed ? "Hide gold answer" : "Reveal gold answer"} <kbd>G</kbd>
        </button>
        <AnimatePresence initial={false}>{revealed && <GoldPanel c={c} />}</AnimatePresence>
      </section>
    </article>
  );
}
