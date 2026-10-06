import { Link } from "react-router";
import { useHealth } from "../../api/health";
import { useRunList } from "../../api/admin";
import { pct, useScorecard } from "../../api/scorecard";
import type { ConditionId } from "../../api/runs";
import { CONDITIONS } from "../../app/conditions";
import { Switchboard } from "../../components/Switchboard";
import { DotWhisker } from "../scorecard/DotWhisker";
import "../data/data.css";
import "../scorecard/scorecard.css";
import "./overview.css";
import { PageTitle } from "../../components/PageHeader";
import { SectionTitle } from "../../components/Ink";

export function OverviewPage() {
  const { data: health } = useHealth();
  const { data: sc, error: scError } = useScorecard(null);
  const { data: runs } = useRunList();

  const conds = sc?.conditions ?? [];
  const first = conds[0] as ConditionId | undefined;
  const last = conds[conds.length - 1] as ConditionId | undefined;
  const m = (key: string) => sc?.metrics.find((x) => x.key === key);
  const rate = (key: string, c: ConditionId | undefined) => (c ? m(key)?.by_condition[c]?.rate ?? null : null);
  const danger = m("dangerous");

  return (
    <div className="datapage overview" data-testid="overview-page">
      <header className="dp-header">
        <div>
          <PageTitle plate="08">VetAgentBench-IN</PageTitle>
          <p className="dp-sub">A field-station notebook on whether agent machinery makes veterinary advice safer.</p>
        </div>
        <button type="button" className="btn no-print" onClick={() => window.print()}>
          Print
        </button>
      </header>

      <div className="grid-12 ov-spread">
        <div className="span-7 ov-text">
          <p className="ov-lede">
            Does giving a language model retrieval, tools, self-verification and hard safety rules make its veterinary
            advice <em>safer</em>?
          </p>
          <p className="ov-para">
            The same India-focused, livestock-heavy cases are examined under five conditions, each adding one piece of
            machinery to a bare model. Every answer has the same schema, so the conditions can be compared case by case.
          </p>
          <p className="ov-para">
            We count accuracy, but above all dangerous errors: a banned drug called safe, an emergency sent home, a withdrawal
            period invented. Guidance comes from India&rsquo;s Standard Veterinary Treatment Guidelines.
          </p>
          <ol className="marginalia ov-notes">
            <li>
              <strong>Research prototype.</strong> Not clinical advice; every gold answer and drug row awaits a
              veterinarian&rsquo;s verification.
            </li>
            <li>
              <strong>Mode</strong> {health ? (health.mode === "live" ? `live · ${health.model}` : "demo — sample responses") : "—"}.
            </li>
          </ol>
        </div>

        <dl className="span-5 ov-strip ov-figures" aria-label="The station in figures">
          <div className="ov-fig">
            <dt className="eyebrow">Cases on file</dt>
            <dd className="ov-num serif">{health?.counts.cases ?? "—"}</dd>
          </div>
          <div className="ov-fig">
            <dt className="eyebrow">Conditions</dt>
            <dd className="ov-num serif">{CONDITIONS.length}</dd>
          </div>
          <div className="ov-fig">
            <dt className="eyebrow">Drug-table rows</dt>
            <dd className="ov-num serif">{health?.counts.drugs ?? "—"}</dd>
          </div>
          <div className="ov-fig">
            <dt className="eyebrow">SVTG pages indexed</dt>
            <dd className="ov-num serif">{health?.pages ?? "—"}</dd>
            <dd className="ov-cap mono">{health ? `${health.chunks} passages` : ""}</dd>
          </div>
          <div className="ov-fig">
            <dt className="eyebrow">Runs recorded</dt>
            <dd className="ov-num serif">{health?.counts.runs ?? "—"}</dd>
          </div>
        </dl>
      </div>

      <section className="ov-section">
        <SectionTitle>Five conditions, one answer schema</SectionTitle>
        <div className="ov-conds">
          {CONDITIONS.map((c) => (
            <div key={c.id} className="ov-cond" data-cond={c.id}>
              <div className="ov-cond-head">
                <span className="mono">{c.id}</span> <strong>{c.name}</strong>
              </div>
              <Switchboard condition={c} />
            </div>
          ))}
        </div>
      </section>

      <section className="ov-section">
        <div className="sc-section-head">
          <SectionTitle>Latest results</SectionTitle>
          {sc && (
            <Link className="link-button" to={`/scorecard?run=${encodeURIComponent(sc.run.id)}`}>
              Full lab report
            </Link>
          )}
        </div>
        {scError && <p className="empty-body">{scError.message}</p>}
        {sc && (
          <div className="grid-12">
            <div className="span-4 ov-headline">
              <p className="rv-small mono">
                Run {sc.run.created_at.replace("T", " ").slice(0, 16)} · {sc.run.provider}/{sc.run.model} · {sc.n_cases} cases
              </p>
              <p className="ov-line">
                <span className="eyebrow">
                  Top-1 diagnosis · {first} → {last}
                </span>
                <span className="ov-pair">
                  <span className="serif ov-big">{pct(rate("dx_top1", first))}</span>
                  <span className="ov-arrow">→</span>
                  <span className="serif ov-big">{pct(rate("dx_top1", last))}</span>
                </span>
              </p>
              <p className="ov-line">
                <span className="eyebrow">Any dangerous error · lower is better</span>
                <span className="ov-pair">
                  <span className="serif ov-big">{pct(rate("dangerous", first))}</span>
                  <span className="ov-arrow">→</span>
                  <span className="serif ov-big">{pct(rate("dangerous", last))}</span>
                </span>
              </p>
              {sc.warnings.length > 0 && <p className="rv-small">{sc.warnings[0]}</p>}
            </div>
            <div className="span-8">{danger && <DotWhisker metric={danger} conditions={conds} />}</div>
          </div>
        )}
      </section>

      <div className="grid-12">
        <section className="ov-section span-7">
          <SectionTitle>How to use the station</SectionTitle>
          <ol className="st-list">
            <li>
              <Link to="/">Bench</Link> — mount a specimen, press R, read each condition&rsquo;s instruments.
            </li>
            <li>
              <Link to="/scorecard">Scorecard</Link> — the lab report: rates with 95% intervals, McNemar tests, CSV.
            </li>
            <li>
              <Link to="/review">Review</Link> — a veterinarian rates answers blind; agreement as Cohen&rsquo;s κ.
            </li>
            <li>
              <Link to="/cases">Cases</Link> and <Link to="/drugs">Drug Table</Link> — the ledgers, edited and verified.
            </li>
            <li>
              <Link to="/study">Study design</Link> — conditions, metrics, statistics and limitations.
            </li>
          </ol>
        </section>
        <section className="ov-section span-5">
          <SectionTitle>Recent runs</SectionTitle>
          <ul className="ov-runs">
            {(runs ?? []).slice(0, 5).map((r) => (
              <li key={r.id} className="mono">
                {r.created_at.replace("T", " ").slice(0, 16)} · {r.provider} · {r.case_ids.length}×{r.conditions.length}
                {r.interview ? " · interview" : ""} · {r.status}
              </li>
            ))}
            {runs && runs.length === 0 && <li>No runs recorded yet.</li>}
          </ul>
          <Link className="link-button" to="/runs">
            All runs
          </Link>
        </section>
      </div>
    </div>
  );
}
