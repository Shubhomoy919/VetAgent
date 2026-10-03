import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { formatAge } from "../../api/cases";
import { kappaLabel, saveReview, useReviewQueue, useReviewStats, type Rating, type ReviewItem } from "../../api/admin";
import { pct, useRuns } from "../../api/scorecard";
import { CONDITIONS } from "../../app/conditions";
import { Stamp } from "../../components/Stamp";
import { SpecimenTag, TypePill } from "../../components/Tags";
import "../data/data.css";
import "./review.css";

const REVIEWER_KEY = "vab.reviewer";
const COND_NAME = Object.fromEntries(CONDITIONS.map((c) => [c.id, c.name]));

function readReviewer(): string {
  try {
    return localStorage.getItem(REVIEWER_KEY) ?? "";
  } catch {
    return "";
  }
}

function isTypingTarget(el: EventTarget | null): boolean {
  return el instanceof HTMLElement && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

const RATING_LABEL: Record<Rating, string> = { acceptable: "Acceptable", unacceptable: "Unacceptable", unsure: "Not sure" };

function ItemView({ item, showGold, showMeta }: { item: ReviewItem; showGold: boolean; showMeta: boolean }) {
  const a = item.answer;
  const s = item.case.signalment;
  return (
    <div className="rv-item">
      <section className="rv-case">
        <div className="rv-case-head">
          <SpecimenTag caseId={item.case_id} />
          <TypePill type={item.question_type} />
          <span className="rv-sig mono">
            {item.case.species} · {s.breed} · {formatAge(s.age_months)} · {s.weight_kg} kg{s.lactating ? " · lactating" : ""}
          </span>
        </div>
        <p className="rv-question">{item.case.question}</p>
        <blockquote className="narrative">{item.case.owner_narrative}</blockquote>
        <p className="rv-small">
          <span className="eyebrow">History </span>
          {item.case.history}
        </p>
        <p className="rv-small">
          <span className="eyebrow">Signs </span>
          {item.case.clinical_signs.join(" · ")}
        </p>
      </section>

      <section className="rv-answer" aria-label="Answer under review">
        <div className="rv-answer-head">
          <span className="eyebrow">Answer under review</span>
          {showMeta && (
            <span className="rv-meta mono" data-testid="review-meta">
              {item.condition} {COND_NAME[item.condition]} · auto: {item.auto.dangerous ? "dangerous" : "no dangerous error"}
            </span>
          )}
        </div>
        <p className="rv-dx serif">{a.most_likely}</p>
        {a.differentials.length > 0 && <p className="rv-small">Differentials: {a.differentials.join(" · ")}</p>}
        <dl className="rv-fields">
          <div><dt>Triage</dt><dd className="mono">{a.triage}</dd></div>
          <div><dt>Drug</dt><dd className="mono">{a.drug_status}</dd></div>
          <div><dt>Dose</dt><dd className="mono">{a.dose_mg === null ? "—" : `${a.dose_mg} mg`}</dd></div>
          <div><dt>Withdrawal</dt><dd className="mono">{a.withdrawal_days === null ? "—" : `${a.withdrawal_days} d`}</dd></div>
          <div><dt>Escalate</dt><dd className="mono">{a.escalate ? "yes" : "no"}</dd></div>
          <div><dt>Zoonosis</dt><dd className="mono">{a.zoonosis_warning ? "warn" : "no"}</dd></div>
          <div><dt>See vet</dt><dd className="mono">{a.see_vet ? "yes" : "no"}</dd></div>
        </dl>
        <p className="rv-advice">{a.advice}</p>
        {a.citations.length > 0 && (
          <p className="rv-small mono">Cites: {a.citations.map((c) => `SVTG p.${c.page}`).join(", ")}</p>
        )}
        {showMeta && item.auto.stamps.length > 0 && (
          <div className="rv-stamps">
            {item.auto.stamps.map((st) => <Stamp key={st} kind={st} />)}
          </div>
        )}
      </section>

      {showGold && (
        <section className="rv-gold" data-testid="review-gold">
          <span className="eyebrow">Gold answer (unverified)</span>
          <p className="rv-dx serif">{item.gold.most_likely}</p>
          <p className="rv-small mono">
            triage {item.gold.triage} · drug {item.gold.drug ?? "—"} {item.gold.drug_status !== "n/a" ? `(${item.gold.drug_status})` : ""} · escalate{" "}
            {item.gold.escalate ? "yes" : "no"}
            {item.gold.withdrawal_known !== null && ` · withdrawal ${item.gold.withdrawal_known ? `${item.gold.withdrawal_days} d` : "not stated"}`}
          </p>
          <ul className="rv-points">
            {item.gold.key_points.map((k) => <li key={k}>{k}</li>)}
          </ul>
        </section>
      )}
    </div>
  );
}

function Stats({ runId }: { runId: string | null }) {
  const { data, error } = useReviewStats(runId);
  if (error) return <p className="error-text">{error.message}</p>;
  if (!data) return <p className="empty-body">Loading agreement…</p>;
  return (
    <aside className="rv-stats" data-testid="review-stats">
      <h2 className="sc-h2">Agreement</h2>
      <p className="rv-small">
        Reviewer vs the automatic scorer (auto = acceptable when no dangerous error). “Not sure” is excluded.
      </p>
      {data.reviewers.length === 0 && <p className="empty-body">No reviews for this run yet.</p>}
      {data.reviewers.map((r) => {
        const m = r.vs_auto.matrix;
        return (
          <div key={r.reviewer} className="rv-rev">
            <div className="rv-rev-head">
              <strong>{r.reviewer}</strong>
              <span className="mono rv-small">
                {r.rated}/{data.items_total} rated · {r.unsure} unsure
              </span>
            </div>
            <p className="rv-kappa">
              <span className="serif rv-kappa-num">{r.vs_auto.kappa === null ? "—" : r.vs_auto.kappa.toFixed(2)}</span>
              <span className="rv-small">
                Cohen’s κ ({kappaLabel(r.vs_auto.kappa)}) · {pct(r.vs_auto.percent)} agreement, n={r.vs_auto.n}
              </span>
            </p>
            <table className="rv-matrix" aria-label={`Confusion matrix for ${r.reviewer}`}>
              <thead>
                <tr><th /><th scope="col">auto ok</th><th scope="col">auto danger</th></tr>
              </thead>
              <tbody>
                <tr><th scope="row">reviewer ok</th><td className="mono">{m.acc_acc}</td><td className="mono" data-off>{m.acc_unacc}</td></tr>
                <tr><th scope="row">reviewer not ok</th><td className="mono" data-off>{m.unacc_acc}</td><td className="mono">{m.unacc_unacc}</td></tr>
              </tbody>
            </table>
            <p className="rv-small">
              Judged acceptable:{" "}
              {Object.entries(r.acceptable_by_condition).map(([c, v]) => (
                <span key={c} className="mono rv-cond">{c} {pct(v?.rate)} ({v?.k}/{v?.n})</span>
              ))}
            </p>
          </div>
        );
      })}
      {data.pairs.length > 0 && (
        <>
          <h3 className="sc-h2">Between reviewers</h3>
          {data.pairs.map((p) => (
            <p key={p.a + p.b} className="rv-small mono">
              {p.a} × {p.b}: κ {p.kappa === null ? "—" : p.kappa.toFixed(2)} ({kappaLabel(p.kappa)}), {pct(p.percent)} agreement, n={p.n}
            </p>
          ))}
        </>
      )}
    </aside>
  );
}

export function ReviewPage() {
  const qc = useQueryClient();
  const [reviewer, setReviewer] = useState(readReviewer);
  const [runId, setRunId] = useState<string | null>(null);
  const [onlyUnrated, setOnlyUnrated] = useState(false);
  const [index, setIndex] = useState(0);
  const [showGold, setShowGold] = useState(false);
  const [showMeta, setShowMeta] = useState(false);
  const [note, setNote] = useState("");
  const { data: runs } = useRuns();
  const { data, error, isPending } = useReviewQueue(runId, reviewer.trim());

  const items = useMemo(() => (data?.items ?? []).filter((i) => !onlyUnrated || !i.review), [data, onlyUnrated]);
  const item = items[Math.min(index, Math.max(0, items.length - 1))];
  const ratedCount = (data?.items ?? []).filter((i) => i.review).length;

  // Reset per-item UI when the item (or its saved note) changes — adjust state during render, not in an effect.
  const itemKey = `${item?.result_id ?? ""}|${item?.review?.note ?? ""}`;
  const [lastKey, setLastKey] = useState(itemKey);
  if (itemKey !== lastKey) {
    setLastKey(itemKey);
    setNote(item?.review?.note ?? "");
    setShowGold(false);
    setShowMeta(false);
  }

  const updateReviewer = (v: string) => {
    setReviewer(v);
    try {
      localStorage.setItem(REVIEWER_KEY, v);
    } catch {
      // storage unavailable: name lasts for this session only
    }
  };

  const rate = useCallback(
    async (rating: Rating) => {
      if (!item) return;
      if (!reviewer.trim()) {
        toast.error("Enter your name as reviewer first.");
        return;
      }
      try {
        await saveReview(item.result_id, reviewer.trim(), rating, note);
        await Promise.all([
          qc.invalidateQueries({ queryKey: ["review-queue"] }),
          qc.invalidateQueries({ queryKey: ["review-stats"] }),
        ]);
        if (!onlyUnrated) setIndex((i) => Math.min(i + 1, items.length - 1));
      } catch (e) {
        toast.error(e instanceof Error ? e.message : String(e));
      }
    },
    [item, reviewer, note, qc, onlyUnrated, items.length],
  );

  // 1 = acceptable, 2 = unacceptable, N = not sure; J/K or arrows to move.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target)) return;
      const k = e.key.toLowerCase();
      if (k === "1") void rate("acceptable");
      else if (k === "2") void rate("unacceptable");
      else if (k === "n") void rate("unsure");
      else if (k === "j" || k === "arrowright") setIndex((i) => Math.min(i + 1, items.length - 1));
      else if (k === "k" || k === "arrowleft") setIndex((i) => Math.max(i - 1, 0));
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rate, items.length]);

  const effectiveRun = data?.run.id ?? runId;

  return (
    <div className="datapage" data-testid="review-page">
      <header className="dp-header">
        <div>
          <h1 className="dp-title serif">Review</h1>
          <p className="dp-sub">
            Rate each answer as a clinician would. Condition and automatic verdict stay hidden until you reveal them.
          </p>
        </div>
        <div className="dp-actions">
          <label className="ff-label" htmlFor="reviewer">Reviewer</label>
          <input id="reviewer" className="dp-search rv-name" value={reviewer} onChange={(e) => updateReviewer(e.target.value)} placeholder="Your name" />
          <select className="dp-select" value={effectiveRun ?? ""} onChange={(e) => { setRunId(e.target.value || null); setIndex(0); }} aria-label="Run to review">
            {!effectiveRun && <option value="">Latest</option>}
            {(runs ?? []).filter((r) => r.n_done > 0).map((r) => (
              <option key={r.id} value={r.id}>
                {r.created_at.replace("T", " ").slice(0, 16)} · {r.provider} · {r.case_ids.length}×{r.conditions.length}
              </option>
            ))}
          </select>
          <label className="toggle">
            <input type="checkbox" checked={onlyUnrated} onChange={(e) => { setOnlyUnrated(e.target.checked); setIndex(0); }} />
            Unrated only
          </label>
        </div>
      </header>

      {isPending && <p className="empty-body">Loading answers…</p>}
      {error && (
        <div className="empty">
          <p className="empty-title serif empty-title-lg">Nothing to review</p>
          <p className="error-text" role="alert">{error.message}</p>
        </div>
      )}

      {data && (
        <div className="rv-layout">
          <div className="rv-main">
            <div className="rv-progress mono" aria-live="polite">
              {items.length === 0 ? "All answers rated." : `Answer ${Math.min(index, items.length - 1) + 1} of ${items.length}`} · {ratedCount}/{data.items.length} rated by{" "}
              {reviewer.trim() || "—"}
              <span className="progress rv-bar"><span className="progress-fill" style={{ width: `${data.items.length ? (ratedCount / data.items.length) * 100 : 0}%` }} /></span>
            </div>

            {item && (
              <>
                <ItemView item={item} showGold={showGold} showMeta={showMeta} />
                <div className="rv-reveal">
                  <button type="button" className="btn" aria-pressed={showGold} onClick={() => setShowGold(!showGold)}>
                    {showGold ? "Hide gold" : "Show gold"}
                  </button>
                  <button type="button" className="btn" aria-pressed={showMeta} onClick={() => setShowMeta(!showMeta)}>
                    {showMeta ? "Hide condition & auto verdict" : "Reveal condition & auto verdict"}
                  </button>
                  {item.review && (
                    <span className="rv-current mono" data-rating={item.review.rating}>
                      your rating: {RATING_LABEL[item.review.rating]}
                    </span>
                  )}
                </div>
                <label className="ff-label" htmlFor="rv-note">Note (optional)</label>
                <textarea id="rv-note" className="ff-input ff-textarea" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
                <div className="rv-actions" role="group" aria-label="Rate this answer">
                  <button type="button" className="btn rv-btn" data-rating="acceptable" onClick={() => void rate("acceptable")} data-testid="rate-1">
                    <kbd>1</kbd> Acceptable
                  </button>
                  <button type="button" className="btn rv-btn" data-rating="unacceptable" onClick={() => void rate("unacceptable")} data-testid="rate-2">
                    <kbd>2</kbd> Unacceptable
                  </button>
                  <button type="button" className="btn rv-btn" data-rating="unsure" onClick={() => void rate("unsure")} data-testid="rate-n">
                    <kbd>N</kbd> Not sure
                  </button>
                  <span className="rv-nav">
                    <button type="button" className="btn" onClick={() => setIndex((i) => Math.max(i - 1, 0))} aria-label="Previous answer">← K</button>
                    <button type="button" className="btn" onClick={() => setIndex((i) => Math.min(i + 1, items.length - 1))} aria-label="Next answer">J →</button>
                  </span>
                </div>
              </>
            )}
          </div>
          <Stats runId={effectiveRun} />
        </div>
      )}
    </div>
  );
}
