import { useIsAdmin } from "../../api/auth";
import { ReadOnlyNote } from "../../app/Access";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import type { DrugStatus } from "../../api/cases";
import { ApiError, drugKey, importDrugs, useDrugs, type DrugRow } from "../../api/data";
import { SortTh } from "../../components/SortTh";
import { UnverifiedTag } from "../../components/Tags";
import { useSort } from "../../components/useSort";
import "../data/data.css";
import { DrugEditor } from "./DrugEditor";
import { PageTitle } from "../../components/PageHeader";

const DRUG_STATUS_LABEL = { safe: "Safe", contraindicated: "Contraindicated", banned_in_india: "Banned in India" } as const;

const SORT = {
  species: (r: DrugRow) => r.species,
  drug: (r: DrugRow) => r.drug,
  status: (r: DrugRow) => ({ banned_in_india: 0, contraindicated: 1, safe: 2 })[r.status],
  dose: (r: DrugRow) => r.dose_min_mg_per_kg,
  milk: (r: DrugRow) => r.milk_withdrawal_days,
  meat: (r: DrugRow) => r.meat_withdrawal_days,
  legal: (r: DrugRow) => r.legal_in_india,
  source: (r: DrugRow) => r.source,
  verified: (r: DrugRow) => r.verified,
};
type SortKey = keyof typeof SORT;
const STATUSES: DrugStatus[] = ["safe", "contraindicated", "banned_in_india"];
const fmt = (v: number | null) => (v === null ? "—" : String(v));

export function DrugsPage() {
  const qc = useQueryClient();
  const { data: rows, error, isPending } = useDrugs();
  const [q, setQ] = useState("");
  const [species, setSpecies] = useState("ALL");
  const [status, setStatus] = useState<DrugStatus | "ALL">("ALL");
  const [editing, setEditing] = useState<DrugRow | null | "new">(null);
  const admin = useIsAdmin();
  const [importMode, setImportMode] = useState<"merge" | "replace">("merge");
  const fileRef = useRef<HTMLInputElement>(null);

  const speciesList = useMemo(() => [...new Set((rows ?? []).map((r) => r.species))].sort(), [rows]);
  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase();
    return (rows ?? []).filter(
      (r) =>
        (species === "ALL" || r.species === species) &&
        (status === "ALL" || r.status === status) &&
        (!t || `${r.drug} ${r.species} ${r.source} ${r.notes}`.toLowerCase().includes(t)),
    );
  }, [rows, q, species, status]);
  const { sorted, key, dir, toggle } = useSort<DrugRow, SortKey>(filtered, SORT, "species");

  const onImport = async (file: File) => {
    try {
      if (importMode === "replace" && !window.confirm("Replace the WHOLE drug table with the imported CSV?")) return;
      const r = await importDrugs(await file.text(), importMode);
      await qc.invalidateQueries({ queryKey: ["drugs"] });
      toast(`Imported ${r.imported} row(s) · ${r.total} total`);
    } catch (e) {
      if (e instanceof ApiError && e.errors.length) {
        toast.error(`${e.message}: ${e.errors.slice(0, 3).map((x) => `${x.loc.join(".")}: ${x.msg}`).join("; ")}`);
      } else toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const unverified = (rows ?? []).filter((r) => !r.verified).length;

  return (
    <div className="datapage" data-testid="drugs-page">
      <header className="dp-header">
        <div>
          <PageTitle plate="05">Drug table</PageTitle>
          <p className="dp-sub">
            {rows ? `${rows.length} rows · ${unverified} unverified` : "Loading"} · doses and withdrawal periods only where a
            source states them · stored in <span className="mono">data/drug_table.csv</span>
          </p>
        </div>
        <div className="dp-actions">
          {!admin && <ReadOnlyNote what="Edit the drug table" />}
          {admin && (
          <>
          <button type="button" className="btn btn-primary" onClick={() => setEditing("new")}>
            New row
          </button>
          <label className="toggle dp-import-mode">
            Import
            <select value={importMode} onChange={(e) => setImportMode(e.target.value as "merge" | "replace")} aria-label="Import mode">
              <option value="merge">merge</option>
              <option value="replace">replace</option>
            </select>
          </label>
          <button type="button" className="btn" onClick={() => fileRef.current?.click()}>
            Import CSV
          </button>
          <input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) void onImport(f); }} />
          </>
          )}
          <a className="btn" href="/api/drugs/export" download>
            Export CSV
          </a>
        </div>
      </header>

      <div className="dp-filters">
        <label className="visually-hidden" htmlFor="drug-search">
          Search drugs
        </label>
        <input id="drug-search" className="dp-search" type="search" placeholder="Search drug, source, notes…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="dp-select" value={species} onChange={(e) => setSpecies(e.target.value)} aria-label="Filter by species">
          <option value="ALL">All species</option>
          {speciesList.map((sp) => (
            <option key={sp} value={sp}>
              {sp}
            </option>
          ))}
        </select>
        <div className="chip-row" role="group" aria-label="Filter by status">
          <button type="button" className="chip" aria-pressed={status === "ALL"} onClick={() => setStatus("ALL")}>
            All
          </button>
          {STATUSES.map((st) => (
            <button key={st} type="button" className="chip" aria-pressed={status === st} onClick={() => setStatus(status === st ? "ALL" : st)}>
              {DRUG_STATUS_LABEL[st]}
            </button>
          ))}
        </div>
        <span className="dp-count mono" aria-live="polite">
          {sorted.length} shown
        </span>
      </div>

      {isPending && <p className="empty-body">Loading drug table…</p>}
      {error && <p className="error-text" role="alert">{error.message}</p>}

      {rows && (
        <div className="dp-table-wrap">
          <table className="dp-table ledger" data-testid="drugs-table">
            <thead>
              <tr>
                <SortTh label="Species" k="species" sortKey={key} dir={dir} onSort={toggle} />
                <SortTh label="Drug" k="drug" sortKey={key} dir={dir} onSort={toggle} />
                <SortTh label="Vet check" k="verified" sortKey={key} dir={dir} onSort={toggle} />
                <SortTh label="Status" k="status" sortKey={key} dir={dir} onSort={toggle} />
                <SortTh label="Dose mg/kg" k="dose" sortKey={key} dir={dir} onSort={toggle} className="num" />
                <SortTh label="Milk wd" k="milk" sortKey={key} dir={dir} onSort={toggle} className="num" />
                <SortTh label="Meat wd" k="meat" sortKey={key} dir={dir} onSort={toggle} className="num" />
                <SortTh label="Legal" k="legal" sortKey={key} dir={dir} onSort={toggle} />
                <SortTh label="Source" k="source" sortKey={key} dir={dir} onSort={toggle} />
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr
                  key={drugKey(r)}
                  tabIndex={admin ? 0 : undefined}
                  data-drug-key={drugKey(r)}
                  data-editable={admin}
                  onClick={admin ? () => setEditing(r) : undefined}
                  onKeyDown={admin ? (e) => { if (e.key === "Enter") setEditing(r); } : undefined}
                  aria-label={admin ? `Edit ${r.drug} for ${r.species}` : undefined}
                >
                  <td className="cap">{r.species}</td>
                  <td>{r.drug}</td>
                  <td>{r.verified ? <span className="verified-tag" title={`${r.verified_by}, ${r.verified_on}`}>Verified</span> : <UnverifiedTag />}</td>
                  <td>
                    <span className="status-pill" data-status={r.status}>{DRUG_STATUS_LABEL[r.status]}</span>
                  </td>
                  <td className="num mono">
                    {r.dose_min_mg_per_kg === null ? "—" : r.dose_min_mg_per_kg === r.dose_max_mg_per_kg ? fmt(r.dose_min_mg_per_kg) : `${fmt(r.dose_min_mg_per_kg)}–${fmt(r.dose_max_mg_per_kg)}`}
                  </td>
                  <td className="num mono">{r.milk_withdrawal_days === null ? "—" : `${r.milk_withdrawal_days} d`}</td>
                  <td className="num mono">{r.meat_withdrawal_days === null ? "—" : `${r.meat_withdrawal_days} d`}</td>
                  <td className="mono" data-bad={!r.legal_in_india}>{r.legal_in_india ? "Yes" : "No"}</td>
                  <td className="wrap">{r.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <DrugEditor open={editing !== null} initial={editing === "new" ? null : editing} onClose={() => setEditing(null)} />
    </div>
  );
}
