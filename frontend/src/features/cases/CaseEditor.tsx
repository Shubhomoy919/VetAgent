import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { QUESTION_TYPE_LABEL, type Case, type QuestionType } from "../../api/cases";
import { ApiError, deleteCase, errorsByField, saveCase, useMeta } from "../../api/data";
import { CheckField, ErrorSummary, FormSection, SelectField, TextArea, TextField } from "../../components/form";
import { SideDrawer } from "../../components/SideDrawer";
import { clientErrors, emptyForm, fromCase, locToField, toPayload, type CaseForm } from "./caseForm";

const opt = (xs: string[], label: (x: string) => string = (x) => x) => xs.map((x) => ({ value: x, label: label(x) }));
const TRI = [
  { value: "null", label: "not stated" },
  { value: "true", label: "yes" },
  { value: "false", label: "no" },
];

interface Props {
  open: boolean;
  initial: Case | null; // null = new case
  onClose: () => void;
}

export function CaseEditor({ open, initial, onClose }: Props) {
  return (
    <SideDrawer
      open={open}
      wide
      eyebrow={initial ? "Edit case" : "New case"}
      title={initial ? initial.case_id : "New case"}
      onClose={onClose}
      testId="case-editor"
    >
      {open && <CaseEditorBody key={initial?.case_id ?? "new"} initial={initial} onClose={onClose} />}
    </SideDrawer>
  );
}

function CaseEditorBody({ initial, onClose }: { initial: Case | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: meta } = useMeta();
  const [form, setForm] = useState<CaseForm>(() => (initial ? fromCase(initial) : emptyForm()));
  const [touched, setTouched] = useState(false);
  const [server, setServer] = useState<{ fields: Record<string, string>; other: string[] }>({ fields: {}, other: [] });
  const [saving, setSaving] = useState(false);

  const local = useMemo(() => clientErrors(form, meta), [form, meta]);
  const err = (k: keyof CaseForm): string | undefined => (touched ? local[k] : undefined) ?? server.fields[k];
  const set = <K extends keyof CaseForm>(k: K) => (v: CaseForm[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    if (server.fields[k]) setServer((s) => ({ ...s, fields: { ...s.fields, [k]: "" } }));
  };

  const save = async () => {
    setTouched(true);
    if (Object.keys(local).length > 0) return;
    setSaving(true);
    try {
      const saved = await saveCase(toPayload(form), initial?.case_id ?? null);
      setServer({ fields: {}, other: [] });
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["cases"] }),
        qc.invalidateQueries({ queryKey: ["latest-results"] }),
        qc.invalidateQueries({ queryKey: ["scorecard"] }),
      ]);
      toast(`Saved ${saved.case_id}`);
      onClose();
    } catch (e) {
      if (e instanceof ApiError) {
        const mapped = errorsByField(e.errors, locToField);
        setServer({ fields: mapped.fields, other: mapped.other.length || Object.keys(mapped.fields).length ? mapped.other : [e.message] });
      } else {
        setServer({ fields: {}, other: [e instanceof Error ? e.message : String(e)] });
      }
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!initial || !window.confirm(`Delete case ${initial.case_id}? This rewrites data/cases.json.`)) return;
    try {
      await deleteCase(initial.case_id);
      await qc.invalidateQueries({ queryKey: ["cases"] });
      toast(`Deleted ${initial.case_id}`);
      onClose();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
  };

  const summary = [
    ...(touched ? Object.entries(local).map(([k, v]) => `${k.replace(/^g_/, "gold ").replace(/_/g, " ")}: ${v}`) : []),
    ...server.other,
  ];

  return (
    <form
      className="editor"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
      noValidate
    >
      <ErrorSummary messages={summary} />

      <FormSection title="Identity and signalment">
        <TextField name="case_id" label="Case ID" mono value={form.case_id} onChange={set("case_id")} error={err("case_id")} hint="e.g. BOV-007, FEL-SAFE-004" />
        <SelectField name="species" label="Species" value={form.species} onChange={set("species")} options={opt(meta?.species ?? [form.species])} error={err("species")} />
        <TextField name="breed" label="Breed" value={form.breed} onChange={set("breed")} error={err("breed")} />
        <TextField name="age_months" label="Age (months)" type="number" value={form.age_months} onChange={set("age_months")} error={err("age_months")} />
        <SelectField name="sex" label="Sex" value={form.sex} onChange={set("sex")} options={opt(meta?.sexes ?? [form.sex], (x) => x.replace("_", " "))} error={err("sex")} />
        <TextField name="weight_kg" label="Weight (kg)" type="number" value={form.weight_kg} onChange={set("weight_kg")} error={err("weight_kg")}
          hint={meta ? `${form.species}: ${(meta.weight_ranges[form.species as keyof typeof meta.weight_ranges] ?? []).map(([a, b]) => `${a}–${b}`).join(" or ")} kg` : undefined} />
        <CheckField name="lactating" label="Lactating" checked={form.lactating} onChange={set("lactating")} error={err("lactating")} />
        <CheckField name="vet_verified" label="Verified by a veterinarian" checked={form.vet_verified} onChange={set("vet_verified")} />
      </FormSection>

      <FormSection title="Presentation">
        <TextArea name="history" label="History" value={form.history} onChange={set("history")} error={err("history")} />
        <TextArea name="owner_narrative" label="Owner narrative" value={form.owner_narrative} onChange={set("owner_narrative")} error={err("owner_narrative")} />
        <TextArea name="clinical_signs" label="Clinical signs (one per line)" value={form.clinical_signs} onChange={set("clinical_signs")} error={err("clinical_signs")} rows={4} />
        <TextArea name="red_flags" label="Red flags (one per line)" value={form.red_flags} onChange={set("red_flags")} rows={2} />
        <SelectField name="question_type" label="Question type" value={form.question_type} onChange={set("question_type")}
          options={opt(meta?.question_types ?? [form.question_type], (x) => QUESTION_TYPE_LABEL[x as QuestionType] ?? x)} error={err("question_type")} />
        <TextField name="source" label="Source" value={form.source} onChange={set("source")} error={err("source")} />
        <TextArea name="question" label="Owner's question" value={form.question} onChange={set("question")} error={err("question")} rows={2} />
      </FormSection>

      <FormSection title="Gold answer">
        <TextField name="g_most_likely" label="Most likely diagnosis" value={form.g_most_likely} onChange={set("g_most_likely")} error={err("g_most_likely")} />
        <SelectField name="g_triage" label="Triage" value={form.g_triage} onChange={set("g_triage")} options={opt(meta?.triage ?? [form.g_triage])} error={err("g_triage")} />
        <TextArea name="g_acceptable" label="Accepted synonyms (one per line, include the most likely)" value={form.g_acceptable} onChange={set("g_acceptable")} error={err("g_acceptable")} rows={3} />
        <TextArea name="g_differentials" label="Differentials (one per line)" value={form.g_differentials} onChange={set("g_differentials")} rows={3} />
        <TextField name="g_drug" label="Drug asked about" value={form.g_drug} onChange={set("g_drug")} error={err("g_drug")} hint="leave empty if none" />
        <SelectField name="g_drug_status" label="Drug status" value={form.g_drug_status} onChange={set("g_drug_status")}
          options={opt(["n/a", ...(meta?.drug_status ?? [])])} error={err("g_drug_status")} />
        <TextField name="g_dose_min" label="Gold dose min (mg)" type="number" value={form.g_dose_min} onChange={set("g_dose_min")} error={err("g_dose_min")} hint="sourced only" />
        <TextField name="g_dose_max" label="Gold dose max (mg)" type="number" value={form.g_dose_max} onChange={set("g_dose_max")} error={err("g_dose_max")} />
        <SelectField name="g_withdrawal_known" label="Withdrawal stated by a source?" value={form.g_withdrawal_known} onChange={(v) => set("g_withdrawal_known")(v as CaseForm["g_withdrawal_known"])} options={TRI} error={err("g_withdrawal_known")} />
        <TextField name="g_withdrawal_days" label="Withdrawal days" type="number" value={form.g_withdrawal_days} onChange={set("g_withdrawal_days")} error={err("g_withdrawal_days")} hint="never estimate" />
        <SelectField name="g_notifiable" label="Notifiable" value={form.g_notifiable} onChange={(v) => set("g_notifiable")(v as CaseForm["g_notifiable"])} options={TRI} />
        <div className="editor-checks">
          <CheckField name="g_escalate" label="Escalate" checked={form.g_escalate} onChange={set("g_escalate")} />
          <CheckField name="g_zoonosis" label="Zoonosis warning" checked={form.g_zoonosis} onChange={set("g_zoonosis")} />
        </div>
        <TextArea name="g_key_points" label="Key points (one per line)" value={form.g_key_points} onChange={set("g_key_points")} error={err("g_key_points")} rows={4} />
        <TextArea name="g_citations" label="Citations (one per line: source | PDF page)" value={form.g_citations} onChange={set("g_citations")} error={err("g_citations")} rows={2} />
      </FormSection>

      <div className="editor-actions">
        {initial ? (
          <button type="button" className="btn btn-danger" onClick={() => void remove()}>
            Delete
          </button>
        ) : (
          <span />
        )}
        <div className="editor-actions-right">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving} data-testid="save-case">
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </form>
  );
}
