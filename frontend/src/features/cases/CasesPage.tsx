import { useIsAdmin } from "../../api/auth";
import { ReadOnlyNote } from "../../app/Access";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  QUESTION_TYPE_LABEL,
  SPECIES_CODES,
  SPECIES_CODE_LABEL,
  formatAge,
  speciesCode,
  useCases,
  type Case,
  type QuestionType,
  type SpeciesCode,
} from "../../api/cases";
import { ApiError, importCases } from "../../api/data";
import { SortTh } from "../../components/SortTh";
import { SpecimenTag, TypePill, UnverifiedTag } from "../../components/Tags";
import { useSort } from "../../components/useSort";
import "../data/data.css";
import { CaseEditor } from "./CaseEditor";
import { PageTitle } from "../../components/PageHeader";

const TRIAGE_LABEL = { emergency: "Emergency", urgent: "Urgent", routine: "Routine" } as const;

const SORT = {
  id: (c: Case) => c.case_id,
  species: (c: Case) => c.species,
  breed: (c: Case) => c.signalment.breed,
  weight: (c: Case) => c.signalment.weight_kg,
  age: (c: Case) => c.signalment.age_months,
  type: (c: Case) => c.question_type,
  dx: (c: Case) => c.gold_answer.most_likely,
  triage: (c: Case) => ({ emergency: 0, urgent: 1, routine: 2 })[c.gold_answer.triage],
  verified: (c: Case) => c.vet_verified,
};
type SortKey = keyof typeof SORT;
const TYPES = Object.keys(QUESTION_TYPE_LABEL) as QuestionType[];

export function CasesPage() {
  const qc = useQueryClient();
  const { data: cases, error, isPending } = useCases();
  const [q, setQ] = useState("");
  const [species, setSpecies] = useState<SpeciesCode | "ALL">("ALL");
  const [type, setType] = useState<QuestionType | "ALL">("ALL");
  const [verified, setVerified] = useState<"all" | "unverified" | "verified">("all");
  const [editing, setEditing] = useState<Case | null | "new">(null);
  const admin = useIsAdmin();
  const [importMode, setImportMode] = useState<"merge" | "replace">("merge");
  const fileRef = useRef<HTMLInputElement>(null);

  const filtered = useMemo(() => {
    const terms = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return (cases ?? []).filter((c) => {
      if (species !== "ALL" && speciesCode(c.case_id) !== species) return false;
      if (type !== "ALL" && c.question_type !== type) return false;
      if (verified === "verified" && !c.vet_verified) return false;
      if (verified === "unverified" && c.vet_verified) return false;
      const hay = `${c.case_id} ${c.species} ${c.signalment.breed} ${c.gold_answer.most_likely} ${c.question}`.toLowerCase();
      return terms.every((t) => hay.includes(t));
    });
  }, [cases, q, species, type, verified]);

  const { sorted, key, dir, toggle } = useSort<Case, SortKey>(filtered, SORT, "id");

  const onImport = async (file: File) => {
    try {
      const items: unknown = JSON.parse(await file.text());
      if (importMode === "replace" && !window.confirm("Replace ALL cases with the imported file?")) return;
      const r = await importCases(items, importMode);
      await qc.invalidateQueries({ queryKey: ["cases"] });
      toast(`Imported ${r.imported} case(s) · ${r.total} total`);
    } catch (e) {
      if (e instanceof ApiError && e.errors.length) {
        toast.error(`${e.message}: ${e.errors.slice(0, 3).map((x) => `${x.loc.join(".")}: ${x.msg}`).join("; ")}`);
      } else toast.error(e instanceof SyntaxError ? `Not valid JSON: ${e.message}` : e instanceof Error ? e.message : String(e));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const unverifiedCount = (cases ?? []).filter((c) => !c.vet_verified).length;

  return (
    <div className="datapage" data-testid="cases-page">
      <header className="dp-header">
        <div>
          <PageTitle plate="04">Cases</PageTitle>
          <p className="dp-sub">
            {cases ? `${cases.length} cases · ${unverifiedCount} unverified` : "Loading"} · stored in{" "}
            <span className="mono">data/cases.json</span>
          </p>
        </div>
        <div className="dp-actions">
          {!admin && <ReadOnlyNote what="Edit cases" />}
          {admin && (
          <>
          <button type="button" className="btn btn-primary" onClick={() => setEditing("new")}>
            New case
          </button>
          <label className="toggle dp-import-mode">
            Import
            <select value={importMode} onChange={(e) => setImportMode(e.target.value as "merge" | "replace")} aria-label="Import mode">
              <option value="merge">merge</option>
              <option value="replace">replace</option>
            </select>
          </label>
          <button type="button" className="btn" onClick={() => fileRef.current?.click()}>
            Import JSON
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void onImport(f);
            }}
          />
          </>
          )}
          <a className="btn" href="/api/cases/export" download>
            Export JSON
          </a>
        </div>
      </header>

      <div className="dp-filters">
        <label className="visually-hidden" htmlFor="cases-search">
          Search cases
        </label>
        <input id="cases-search" className="dp-search" type="search" placeholder="Search ID, breed, diagnosis, question…" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="chip-row" role="group" aria-label="Filter by species">
          <button type="button" className="chip" aria-pressed={species === "ALL"} onClick={() => setSpecies("ALL")}>
            All
          </button>
          {SPECIES_CODES.map((s) => (
            <button key={s} type="button" className="chip mono" data-species={s} aria-pressed={species === s} title={SPECIES_CODE_LABEL[s]} onClick={() => setSpecies(species === s ? "ALL" : s)}>
              {s}
            </button>
          ))}
        </div>
        <select className="dp-select" value={type} onChange={(e) => setType(e.target.value as QuestionType | "ALL")} aria-label="Filter by question type">
          <option value="ALL">All question types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {QUESTION_TYPE_LABEL[t]}
            </option>
          ))}
        </select>
        <select className="dp-select" value={verified} onChange={(e) => setVerified(e.target.value as typeof verified)} aria-label="Filter by verification">
          <option value="all">Verified and unverified</option>
          <option value="unverified">Unverified only</option>
          <option value="verified">Verified only</option>
        </select>
        <span className="dp-count mono" aria-live="polite">
          {sorted.length} shown
        </span>
      </div>

      {isPending && <p className="empty-body">Loading cases…</p>}
      {error && (
        <p className="error-text" role="alert">
          {error.message}
        </p>
      )}

      {cases && (
        <div className="dp-table-wrap">
          <table className="dp-table ledger" data-testid="cases-table">
            <thead>
              <tr>
                <SortTh label="Case" k="id" sortKey={key} dir={dir} onSort={toggle} />
                <SortTh label="Vet check" k="verified" sortKey={key} dir={dir} onSort={toggle} />
                <SortTh label="Species" k="species" sortKey={key} dir={dir} onSort={toggle} />
                <SortTh label="Breed" k="breed" sortKey={key} dir={dir} onSort={toggle} />
                <SortTh label="Weight" k="weight" sortKey={key} dir={dir} onSort={toggle} className="num" />
                <SortTh label="Age" k="age" sortKey={key} dir={dir} onSort={toggle} className="num" />
                <SortTh label="Type" k="type" sortKey={key} dir={dir} onSort={toggle} />
                <SortTh label="Gold diagnosis" k="dx" sortKey={key} dir={dir} onSort={toggle} />
                <SortTh label="Triage" k="triage" sortKey={key} dir={dir} onSort={toggle} />
              </tr>
            </thead>
            <tbody>
              {sorted.map((c) => (
                <tr
                  key={c.case_id}
                  tabIndex={admin ? 0 : undefined}
                  data-case-id={c.case_id}
                  data-editable={admin}
                  onClick={admin ? () => setEditing(c) : undefined}
                  onKeyDown={
                    admin
                      ? (e) => {
                          if (e.key === "Enter") setEditing(c);
                        }
                      : undefined
                  }
                  aria-label={admin ? `Edit ${c.case_id}` : undefined}
                >
                  <td>
                    <SpecimenTag caseId={c.case_id} />
                  </td>
                  <td>{c.vet_verified ? <span className="verified-tag">Verified</span> : <UnverifiedTag />}</td>
                  <td className="cap">{c.species}</td>
                  <td>{c.signalment.breed}</td>
                  <td className="num mono">{c.signalment.weight_kg} kg</td>
                  <td className="num mono">{formatAge(c.signalment.age_months)}</td>
                  <td>
                    <TypePill type={c.question_type} />
                  </td>
                  <td>{c.gold_answer.most_likely}</td>
                  <td className="mono" data-triage={c.gold_answer.triage}>
                    {TRIAGE_LABEL[c.gold_answer.triage]}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CaseEditor open={editing !== null} initial={editing === "new" ? null : editing} onClose={() => setEditing(null)} />
    </div>
  );
}
