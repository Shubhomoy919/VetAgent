import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { ApiError, deleteDrug, drugKey, errorsByField, saveDrug, useMeta, type DrugRow } from "../../api/data";
import { CheckField, ErrorSummary, FormSection, SelectField, TextArea, TextField } from "../../components/form";
import { SideDrawer } from "../../components/SideDrawer";

interface DrugForm {
  species: string;
  drug: string;
  status: string;
  dose_min: string;
  dose_max: string;
  milk: string;
  meat: string;
  legal: boolean;
  source: string;
  notes: string;
  verified_by: string;
  verified_on: string;
}

const s = (n: number | null) => (n === null ? "" : String(n));
const n = (v: string): number | string | null => {
  const t = v.trim();
  if (!t) return null;
  const x = Number(t);
  return Number.isFinite(x) ? x : t;
};

function fromRow(r: DrugRow | null): DrugForm {
  if (!r) {
    return { species: "cattle", drug: "", status: "safe", dose_min: "", dose_max: "", milk: "", meat: "", legal: true, source: "", notes: "", verified_by: "", verified_on: "" };
  }
  return {
    species: r.species, drug: r.drug, status: r.status, dose_min: s(r.dose_min_mg_per_kg), dose_max: s(r.dose_max_mg_per_kg),
    milk: s(r.milk_withdrawal_days), meat: s(r.meat_withdrawal_days), legal: r.legal_in_india, source: r.source,
    notes: r.notes, verified_by: r.verified_by, verified_on: r.verified_on,
  };
}

function toPayload(f: DrugForm) {
  return {
    species: f.species, drug: f.drug.trim(), status: f.status, dose_min_mg_per_kg: n(f.dose_min), dose_max_mg_per_kg: n(f.dose_max),
    milk_withdrawal_days: n(f.milk), meat_withdrawal_days: n(f.meat), legal_in_india: f.legal, source: f.source,
    notes: f.notes, verified_by: f.verified_by.trim(), verified_on: f.verified_on.trim(),
  };
}

const FIELD: Record<string, keyof DrugForm> = {
  species: "species", drug: "drug", status: "status", dose_min_mg_per_kg: "dose_min", dose_max_mg_per_kg: "dose_max",
  milk_withdrawal_days: "milk", meat_withdrawal_days: "meat", legal_in_india: "legal", source: "source",
  verified_by: "verified_by", verified_on: "verified_on",
};

function clientErrors(f: DrugForm): Partial<Record<keyof DrugForm, string>> {
  const e: Partial<Record<keyof DrugForm, string>> = {};
  if (!f.drug.trim()) e.drug = "Required";
  if (!f.source.trim()) e.source = "Required — cite the page, or say it is unverified";
  const lo = f.dose_min.trim(), hi = f.dose_max.trim();
  if (Boolean(lo) !== Boolean(hi)) e.dose_max = "Give both min and max, or neither";
  else if (lo && hi && Number(lo) > Number(hi)) e.dose_max = "Max must be at least min";
  for (const [k, v] of [["dose_min", lo], ["dose_max", hi], ["milk", f.milk.trim()], ["meat", f.meat.trim()]] as const) {
    if (v && (!Number.isFinite(Number(v)) || Number(v) < 0)) e[k] = "Must be a number ≥ 0";
  }
  if (f.status === "banned_in_india") {
    if (f.legal) e.legal = "A drug banned in India cannot be legal";
    if (lo || hi) e.dose_min = "Banned drugs must not carry a dose";
  }
  if (f.status === "contraindicated" && (lo || hi)) e.dose_min = "Contraindicated drugs must not carry a dose";
  if (Boolean(f.verified_by.trim()) !== Boolean(f.verified_on.trim())) e.verified_on = "Verifier name and date go together";
  return e;
}

export function DrugEditor({ open, initial, onClose }: { open: boolean; initial: DrugRow | null; onClose: () => void }) {
  return (
    <SideDrawer
      open={open}
      eyebrow={initial ? "Edit drug row" : "New drug row"}
      title={initial ? `${initial.drug} · ${initial.species}` : "New drug row"}
      onClose={onClose}
      testId="drug-editor"
    >
      {open && <DrugEditorBody key={initial ? drugKey(initial) : "new"} initial={initial} onClose={onClose} />}
    </SideDrawer>
  );
}

function DrugEditorBody({ initial, onClose }: { initial: DrugRow | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: meta } = useMeta();
  const [form, setForm] = useState<DrugForm>(() => fromRow(initial));
  const [touched, setTouched] = useState(false);
  const [server, setServer] = useState<{ fields: Record<string, string>; other: string[] }>({ fields: {}, other: [] });
  const [saving, setSaving] = useState(false);
  const local = useMemo(() => clientErrors(form), [form]);
  const err = (k: keyof DrugForm) => (touched ? local[k] : undefined) ?? server.fields[k];
  const set = <K extends keyof DrugForm>(k: K) => (v: DrugForm[K]) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setTouched(true);
    if (Object.keys(local).length) return;
    setSaving(true);
    try {
      const saved = await saveDrug(toPayload(form), initial ? drugKey(initial) : null);
      await qc.invalidateQueries({ queryKey: ["drugs"] });
      toast(`Saved ${saved.drug} · ${saved.species}`);
      onClose();
    } catch (e) {
      if (e instanceof ApiError) {
        const m = errorsByField(e.errors, (loc) => FIELD[loc] ?? null);
        setServer({ fields: m.fields, other: m.other.length || Object.keys(m.fields).length ? m.other : [e.message] });
      } else setServer({ fields: {}, other: [e instanceof Error ? e.message : String(e)] });
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!initial || !window.confirm(`Delete ${initial.drug} (${initial.species})? This rewrites data/drug_table.csv.`)) return;
    try {
      await deleteDrug(drugKey(initial));
      await qc.invalidateQueries({ queryKey: ["drugs"] });
      toast(`Deleted ${initial.drug} · ${initial.species}`);
      onClose();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
  };

  const summary = [...(touched ? Object.entries(local).map(([k, v]) => `${k.replace("_", " ")}: ${v}`) : []), ...server.other];

  return (
    <form className="editor" noValidate onSubmit={(e) => { e.preventDefault(); void save(); }}>
      <ErrorSummary messages={summary} />
      <FormSection title="Drug">
        <SelectField name="species" label="Species" value={form.species} onChange={set("species")} options={(meta?.species ?? [form.species]).map((x) => ({ value: x, label: x }))} error={err("species")} />
        <TextField name="drug" label="Drug" value={form.drug} onChange={set("drug")} error={err("drug")} />
        <SelectField name="status" label="Status" value={form.status} onChange={set("status")}
          options={(meta?.drug_status ?? [form.status]).map((x) => ({ value: x, label: x.replace(/_/g, " ") }))} error={err("status")} />
        <CheckField name="legal" label="Legal in India" checked={form.legal} onChange={set("legal")} error={err("legal")} />
      </FormSection>
      <FormSection title="Sourced numbers (leave blank if no source states them)">
        <TextField name="dose_min" label="Dose min (mg/kg)" type="number" value={form.dose_min} onChange={set("dose_min")} error={err("dose_min")} />
        <TextField name="dose_max" label="Dose max (mg/kg)" type="number" value={form.dose_max} onChange={set("dose_max")} error={err("dose_max")} />
        <TextField name="milk" label="Milk withdrawal (days)" type="number" value={form.milk} onChange={set("milk")} error={err("milk")} />
        <TextField name="meat" label="Meat withdrawal (days)" type="number" value={form.meat} onChange={set("meat")} error={err("meat")} />
        <TextField name="source" label="Source (with page)" span={2} value={form.source} onChange={set("source")} error={err("source")} />
        <TextArea name="notes" label="Notes" value={form.notes} onChange={set("notes")} rows={3} />
      </FormSection>
      <FormSection title="Verification">
        <TextField name="verified_by" label="Verified by" value={form.verified_by} onChange={set("verified_by")} error={err("verified_by")} hint="registered veterinarian" />
        <TextField name="verified_on" label="Verified on" type="date" value={form.verified_on} onChange={set("verified_on")} error={err("verified_on")} />
      </FormSection>
      <div className="editor-actions">
        {initial ? <button type="button" className="btn btn-danger" onClick={() => void remove()}>Delete</button> : <span />}
        <div className="editor-actions-right">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={saving} data-testid="save-drug">{saving ? "Saving…" : "Save"}</button>
        </div>
      </div>
    </form>
  );
}
