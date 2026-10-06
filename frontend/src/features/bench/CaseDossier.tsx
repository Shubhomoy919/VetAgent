import { formatAge, formatSex, type Case } from "../../api/cases";
import { useCaseResults } from "../../api/runs";
import { SideDrawer } from "../../components/SideDrawer";
import { Stamp } from "../../components/Stamp";
import { SpecimenTag, TypePill, UnverifiedTag } from "../../components/Tags";
import { Field, GoldPanel } from "./CaseDetail";

interface Props {
  c: Case | null;
  onClose: () => void;
  onCite: (page: number) => void;
}

/** Case dossier: the full case file — signalment, history, narrative, signs, gold answer,
 *  citations, and every past result for this case across runs. */
export function CaseDossier({ c, onClose, onCite }: Props) {
  const { data: past, isPending, error } = useCaseResults(c ? c.case_id : null);
  return (
    <SideDrawer open={c !== null} onClose={onClose} eyebrow="Case dossier" title={c ? c.case_id : ""} wide testId="dossier">
      {c && (
        <div className="dossier">
          <div className="dossier-tags">
            <SpecimenTag caseId={c.case_id} size="lg" />
            <TypePill type={c.question_type} />
            {!c.vet_verified && <UnverifiedTag />}
          </div>
          <dl className="sig-strip" aria-label="Signalment">
            <Field label="Species">{c.species}</Field>
            <Field label="Breed">{c.signalment.breed}</Field>
            <Field label="Age"><span className="mono">{formatAge(c.signalment.age_months)}</span></Field>
            <Field label="Sex">{formatSex(c.signalment.sex)}</Field>
            <Field label="Weight"><span className="mono">{c.signalment.weight_kg} kg</span></Field>
          </dl>

          <section className="dossier-block">
            <h3 className="sc-h3">History</h3>
            <p>{c.history}</p>
          </section>
          <section className="dossier-block">
            <h3 className="sc-h3">Owner narrative</h3>
            <blockquote className="narrative">{c.owner_narrative}</blockquote>
          </section>
          <section className="dossier-block">
            <h3 className="sc-h3">Clinical signs · red flags</h3>
            <ul className="sign-tags">
              {c.clinical_signs.map((s) => <li key={s}>{s}</li>)}
              {c.red_flags.map((f) => <li key={f} className="red-flag">{f}</li>)}
            </ul>
          </section>
          <section className="dossier-block">
            <h3 className="sc-h3">Question</h3>
            <p className="question-text">{c.question}</p>
          </section>

          <section className="dossier-block">
            <h3 className="sc-h3">Gold answer</h3>
            <GoldPanel c={c} onCite={onCite} />
          </section>

          <section className="dossier-block">
            <h3 className="sc-h3">Past results{past ? ` (${past.length})` : ""}</h3>
            {isPending && <p className="empty-body">Loading results…</p>}
            {error && <p className="error-text" role="alert">{error.message}</p>}
            {past && past.length === 0 && <p className="empty-body">This case has not been run yet.</p>}
            {past && past.length > 0 && (
              <table className="dossier-table" data-testid="dossier-results">
                <thead>
                  <tr>
                    <th scope="col">When</th>
                    <th scope="col">Cond.</th>
                    <th scope="col">Model</th>
                    <th scope="col">Most likely</th>
                    <th scope="col">Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {past.map((r) => (
                    <tr key={r.id ?? `${r.run_id}-${r.condition}`}>
                      <td className="mono">{(r.created_at ?? "").replace("T", " ").slice(0, 16)}</td>
                      <td className="mono" data-cond={r.condition}>
                        <span className="led" data-state={r.status === "ok" ? (r.verdict.dangerous ? "danger" : "done") : "error"} /> {r.condition}
                        {r.interview ? " · int." : ""}
                      </td>
                      <td className="mono dossier-model">{r.model ?? r.provider ?? "—"}</td>
                      <td>{r.answer?.most_likely ?? <span className="error-text">error</span>}</td>
                      <td className="dossier-stamps">
                        {r.verdict.stamps.map((s) => (
                          <Stamp key={s} kind={s} seed={String(r.id)} />
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>
      )}
    </SideDrawer>
  );
}
