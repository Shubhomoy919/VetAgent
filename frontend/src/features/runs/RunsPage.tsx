import { Link } from "react-router";
import { useMemo, useState } from "react";
import { useCompare, useRunList, type CompareResult, type RunListRow } from "../../api/admin";
import { pct } from "../../api/scorecard";
import { SpecimenTag } from "../../components/Tags";
import { Stamp } from "../../components/Stamp";
import "../data/data.css";
import "./runs.css";
import { PageTitle } from "../../components/PageHeader";

const fmtDate = (s: string) => s.replace("T", " ").slice(0, 16);
const STATUS: Record<string, string> = { running: "running", done: "done", done_with_errors: "done · errors", cancelled: "cancelled", failed: "failed", quota_exhausted: "quota stop" };

function Delta({ d, better }: { d: number | null; better: "higher" | "lower" }) {
  if (d === null) return <span className="sc-na">—</span>;
  if (Math.abs(d) < 1e-9) return <span className="delta">±0</span>;
  const good = better === "higher" ? d > 0 : d < 0;
  return (
    <span className="delta" data-good={good}>
      {d > 0 ? "+" : "−"}
      {Math.abs(d * 100).toFixed(1)} pt
    </span>
  );
}

function Compare({ data }: { data: CompareResult }) {
  return (
    <section className="cmp" data-testid="compare">
      <div className="cmp-head">
        <h2 className="sc-h2">Compare</h2>
        <p className="dp-sub">
          <strong>A</strong> {fmtDate(data.a.created_at)} · {data.a.provider}/{data.a.model} ·{" "}
          <strong>B</strong> {fmtDate(data.b.created_at)} · {data.b.provider}/{data.b.model} · {data.n_pairs} paired results
        </p>
      </div>
      {data.conditions.length === 0 ? (
        <p className="empty-body">These runs share no conditions.</p>
      ) : (
        <div className="dp-table-wrap">
          <table className="dp-table cmp-table">
            <thead>
              <tr>
                <th scope="col">Metric</th>
                {data.conditions.map((c) => (
                  <th key={c} scope="col" className="mono" data-cond={c}>
                    {c} · A → B
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.metrics.map((m) => (
                <tr key={m.key}>
                  <th scope="row">
                    {m.label} <span className="sc-dir mono">{m.better === "higher" ? "↑" : "↓"}</span>
                  </th>
                  {data.conditions.map((c) => {
                    const v = m.by_condition[c];
                    return (
                      <td key={c} className="mono">
                        {v ? (
                          <>
                            {pct(v.a.rate)} → {pct(v.b.rate)} <Delta d={v.delta} better={m.better} />
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3 className="sc-h2 cmp-sub">Changed verdicts ({data.changes.length})</h3>
      {data.changes.length === 0 ? (
        <p className="empty-body">No case changed verdict between these runs.</p>
      ) : (
        <div className="dp-table-wrap">
          <table className="dp-table" data-testid="compare-changes">
            <thead>
              <tr>
                <th scope="col">Case</th>
                <th scope="col">Condition</th>
                <th scope="col">A</th>
                <th scope="col">B</th>
              </tr>
            </thead>
            <tbody>
              {data.changes.map((ch) => (
                <tr key={ch.case_id + ch.condition} className="nohover">
                  <td>
                    <Link to={`/?case=${ch.case_id}`} className="cmp-case">
                      <SpecimenTag caseId={ch.case_id} />
                    </Link>
                  </td>
                  <td className="mono">{ch.condition}</td>
                  {[ch.a, ch.b].map((s, i) => (
                    <td key={i}>
                      <span className="cmp-stamps">
                        {s.status !== "ok" ? <span className="error-text mono">error</span> : s.stamps.length ? s.stamps.map((st) => <Stamp key={st} kind={st} />) : <span className="sc-na mono">dx wrong · no danger</span>}
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function RunsPage() {
  const { data: runs, error, isPending } = useRunList();
  const [picked, setPicked] = useState<string[]>([]);
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p.slice(-1), id]));

  // A = older, B = newer
  const [a, b] = useMemo(() => {
    if (picked.length < 2 || !runs) return [null, null];
    const order = picked.map((id) => runs.find((r) => r.id === id)).filter(Boolean) as RunListRow[];
    order.sort((x, y) => x.created_at.localeCompare(y.created_at));
    return [order[0]?.id ?? null, order[1]?.id ?? null];
  }, [picked, runs]);
  const cmp = useCompare(a, b);

  return (
    <div className="datapage" data-testid="runs-page">
      <header className="dp-header">
        <div>
          <PageTitle plate="02">Runs</PageTitle>
          <p className="dp-sub">
            {runs ? `${runs.length} runs stored in data/runs.db` : "Loading"} · tick two runs to compare them
          </p>
        </div>
      </header>

      {isPending && <p className="empty-body">Loading runs…</p>}
      {error && <p className="error-text" role="alert">{error.message}</p>}
      {runs && runs.length === 0 && (
        <div className="empty">
          <p className="empty-title serif empty-title-lg">No runs yet</p>
          <p className="empty-body">Run cases from the Bench; every run is listed here.</p>
        </div>
      )}

      {runs && runs.length > 0 && (
        <div className="dp-table-wrap runs-table-wrap">
          <table className="dp-table" data-testid="runs-table">
            <thead>
              <tr>
                <th scope="col"><span className="visually-hidden">Select</span></th>
                <th scope="col">Started</th>
                <th scope="col">Source</th>
                <th scope="col">Provider · model</th>
                <th scope="col">Mode</th>
                <th scope="col" className="num">Cases × cond.</th>
                <th scope="col">Status</th>
                <th scope="col" className="num">Done</th>
                <th scope="col" className="num">Tokens</th>
                <th scope="col" className="num">Errors</th>
                <th scope="col" className="num">Cost</th>
                <th scope="col"><span className="visually-hidden">Open</span></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const sel = picked.includes(r.id);
                return (
                  <tr key={r.id} data-run-id={r.id} aria-selected={sel} onClick={() => toggle(r.id)}>
                    <td>
                      <input
                        type="checkbox"
                        className="case-check"
                        checked={sel}
                        aria-label={`Select run ${r.id} for comparison`}
                        onClick={(e) => e.stopPropagation()}
                        onChange={() => toggle(r.id)}
                      />
                      {sel && <span className="run-pick mono">{r.id === a ? "A" : r.id === b ? "B" : "·"}</span>}
                    </td>
                    <td className="mono">{fmtDate(r.created_at)}</td>
                    <td className="mono">{r.label}</td>
                    <td className="mono">
                      {r.provider}
                      {r.model !== r.provider ? ` · ${r.model}` : ""}
                    </td>
                    <td>{r.interview ? "interview" : "standard"}</td>
                    <td className="num mono">
                      {r.case_ids.length} × {r.conditions.length}
                    </td>
                    <td className="mono" data-bad={r.status === "failed" || r.status === "done_with_errors" || r.status === "quota_exhausted"}>
                      {STATUS[r.status] ?? r.status}
                    </td>
                    <td className="num mono">
                      {r.n_done}/{r.n_total}
                    </td>
                    <td className="num mono">{r.tokens.toLocaleString("en-IN")}</td>
                    <td className="num mono" data-bad={r.errors > 0}>
                      {r.errors}
                    </td>
                    <td className="num mono">{r.cost_usd === null ? "unknown" : `$${r.cost_usd.toFixed(4)}`}</td>
                    <td>
                      <Link to={`/scorecard?run=${encodeURIComponent(r.id)}`} className="link-button" onClick={(e) => e.stopPropagation()}>
                        Scorecard
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {cmp.isFetching && <p className="empty-body">Comparing…</p>}
      {cmp.error && <p className="error-text" role="alert">{cmp.error.message}</p>}
      {cmp.data && <Compare data={cmp.data} />}
    </div>
  );
}
