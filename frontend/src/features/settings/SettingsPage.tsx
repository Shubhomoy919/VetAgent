import { AccessGate } from "../../app/Access";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import {
  resetSettings,
  saveSettings,
  testConnection,
  useSettings,
  useUsage,
  type SettingsValues,
  type SettingsView,
  type TestResult,
} from "../../api/admin";
import { ApiError } from "../../api/data";
import { ErrorSummary, FormSection, SelectField, TextField } from "../../components/form";
import "../data/data.css";
import "./settings.css";
import { PageTitle } from "../../components/PageHeader";

type Form = Record<keyof SettingsValues, string>;

function toForm(v: SettingsValues): Form {
  const out = {} as Form;
  for (const [k, val] of Object.entries(v)) out[k as keyof SettingsValues] = val === null ? "" : String(val);
  return out;
}

const NUMERIC: (keyof SettingsValues)[] = ["temperature", "max_steps", "max_owner_questions", "demo_delay_ms", "price_input_per_mtok", "price_output_per_mtok"];

function toPayload(f: Form): Partial<Record<keyof SettingsValues, unknown>> {
  const out: Partial<Record<keyof SettingsValues, unknown>> = {};
  for (const [k, v] of Object.entries(f) as [keyof SettingsValues, string][]) {
    if (NUMERIC.includes(k)) {
      const t = v.trim();
      out[k] = t === "" ? (k.startsWith("price") ? "" : t) : Number.isFinite(Number(t)) ? Number(t) : t;
    } else out[k] = v.trim();
  }
  return out;
}

function SettingsForm({ view }: { view: SettingsView }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<Form>(() => toForm(view.values));
  const [errors, setErrors] = useState<{ fields: Record<string, string>; other: string[] }>({ fields: {}, other: [] });
  const [saving, setSaving] = useState(false);
  const [test, setTest] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const set = (k: keyof SettingsValues) => (v: string) => setForm((f) => ({ ...f, [k]: v }));
  const tag = (k: keyof SettingsValues) => (view.overridden.includes(k) ? "overridden here" : "from the environment / default");
  const refresh = () =>
    Promise.all(["settings", "health", "usage"].map((k) => qc.invalidateQueries({ queryKey: [k] })));

  const save = async () => {
    // Send only what changed, so untouched settings keep coming from .env.
    const original = toForm(view.values);
    const changed = Object.fromEntries(
      Object.entries(toPayload(form)).filter(([k]) => form[k as keyof SettingsValues] !== original[k as keyof SettingsValues]),
    );
    if (Object.keys(changed).length === 0) {
      toast("Nothing changed");
      return;
    }
    setSaving(true);
    try {
      const v = await saveSettings(changed);
      setErrors({ fields: {}, other: [] });
      setForm(toForm(v.values));
      await refresh();
      toast("Settings saved");
    } catch (e) {
      if (e instanceof ApiError) {
        const fields: Record<string, string> = {};
        const other: string[] = [];
        for (const x of e.errors) {
          const k = String(x.loc[0] ?? "");
          if (k in form && !fields[k]) fields[k] = x.msg;
          else other.push(`${x.loc.join(".")}: ${x.msg}`);
        }
        setErrors({ fields, other: other.length || Object.keys(fields).length ? other : [e.message] });
      } else setErrors({ fields: {}, other: [String(e)] });
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    if (!window.confirm("Remove all overrides and go back to the environment values?")) return;
    const v = await resetSettings();
    setForm(toForm(v.values));
    setErrors({ fields: {}, other: [] });
    await refresh();
    toast("Overrides removed");
  };

  const runTest = async () => {
    setTesting(true);
    try {
      setTest(await testConnection());
    } catch (e) {
      setTest({ ok: false, provider: "", model: "", latency_ms: 0, reply: null, message: e instanceof Error ? e.message : String(e) });
    } finally {
      setTesting(false);
    }
  };

  const err = (k: keyof SettingsValues) => errors.fields[k];

  return (
    <form className="editor st-form" noValidate onSubmit={(e) => { e.preventDefault(); void save(); }}>
      <ErrorSummary messages={errors.other} />

      <FormSection title="Model provider">
        <SelectField name="llm_provider" label="Provider" value={form.llm_provider} onChange={set("llm_provider")} hint={tag("llm_provider")} error={err("llm_provider")}
          options={[{ value: "gemini", label: "Gemini" }, { value: "openai_compatible", label: "OpenAI-compatible" }, { value: "demo", label: "Demo (no model)" }]} />
        <div className="ff">
          <span className="ff-label">API key</span>
          <span className="set-key mono" data-present={view.key_present} data-testid="key-status">
            {view.key_present ? "present (hidden)" : "not set"}
          </span>
          <span className="ff-hint">{view.key_hint}. Keys are never shown or stored here.</span>
        </div>
        {form.llm_provider === "gemini" && (
          <TextField name="gemini_model" label="Model" mono value={form.gemini_model} onChange={set("gemini_model")} hint={tag("gemini_model")} error={err("gemini_model")} />
        )}
        {form.llm_provider === "openai_compatible" && (
          <>
            <TextField name="openai_model" label="Model" mono value={form.openai_model} onChange={set("openai_model")} hint={tag("openai_model")} error={err("openai_model")} />
            <TextField name="openai_base_url" label="Base URL" mono span={2} value={form.openai_base_url} onChange={set("openai_base_url")} hint="e.g. https://api.openai.com/v1" error={err("openai_base_url")} />
          </>
        )}
        <div className="ff set-test" data-span="2">
          <div className="set-test-row">
            <span className="pill" data-tone={view.mode === "live" ? "live" : "demo"}>
              <span className="pill-dot" aria-hidden="true" />
              {view.mode === "live" ? `Live · ${view.model}` : "Demo"}
            </span>
            <button type="button" className="btn" onClick={() => void runTest()} disabled={testing} data-testid="test-connection">
              {testing ? "Testing…" : "Test connection"}
            </button>
          </div>
          {test && (
            <p className="set-test-result mono" data-ok={test.ok} role="status" data-testid="test-result">
              {test.ok ? "OK" : "FAILED"} · {test.message}
              {test.ok && test.provider !== "demo" ? ` · ${test.model} · ${test.latency_ms} ms` : ""}
            </p>
          )}
        </div>
      </FormSection>

      <FormSection title="Agent">
        <TextField name="temperature" label="Temperature" type="number" value={form.temperature} onChange={set("temperature")} hint={`0–2 · ${tag("temperature")}`} error={err("temperature")} />
        <TextField name="max_steps" label="Max tool steps (C2–C4)" type="number" value={form.max_steps} onChange={set("max_steps")} hint={`1–12 · ${tag("max_steps")}`} error={err("max_steps")} />
      </FormSection>


      <FormSection title="Knowledge source (SVTG)">
        <div className="ff" data-span="2">
          <span className="ff-label">Passage index</span>
          <span className="mono set-pdf" data-ok={view.svtg.index_loaded} data-testid="pdf-status">
            {view.svtg.index_loaded
              ? `loaded · ${view.svtg.chunks.toLocaleString("en-US")} passages from ${view.svtg.source_pages} pages`
              : "not loaded · run the seed script with the PDF on your computer"}
          </span>
          <span className="ff-hint">
            Passages are stored in the database by <span className="mono">python -m app.scripts.seed</span>. The PDF
            itself is never deployed.
          </span>
        </div>
      </FormSection>

      <div className="editor-actions">
        <button type="button" className="btn" onClick={() => void reset()} disabled={view.overridden.length === 0}>
          Reset to environment
        </button>
        <div className="editor-actions-right">
          <span className="ff-hint">Saved in the database; overrides the server environment</span>
          <button type="submit" className="btn btn-primary" disabled={saving} data-testid="save-settings">
            {saving ? "Saving…" : "Save settings"}
          </button>
        </div>
      </div>
    </form>
  );
}


function Usage() {
  const { data } = useUsage();
  return (
    <section className="st-usage" data-testid="usage">
      <h2 className="fs-legend">Token and cost totals (all stored results)</h2>
      {!data ? (
        <p className="empty-body">Loading…</p>
      ) : data.by_model.length === 0 ? (
        <p className="empty-body">No results stored yet.</p>
      ) : (
        <div className="dp-table-wrap">
          <table className="dp-table ledger">
            <thead>
              <tr>
                <th scope="col">Provider</th>
                <th scope="col">Model</th>
                <th scope="col" className="num">Results</th>
                <th scope="col" className="num">Tokens in</th>
                <th scope="col" className="num">Tokens out</th>
                <th scope="col" className="num">Cost</th>
              </tr>
            </thead>
            <tbody>
              {data.by_model.map((r) => (
                <tr key={r.provider + r.model} className="nohover">
                  <td className="mono">{r.provider}</td>
                  <td className="mono">{r.model}</td>
                  <td className="num mono">{r.results.toLocaleString("en-US")}</td>
                  <td className="num mono">{r.tokens_in.toLocaleString("en-US")}</td>
                  <td className="num mono">{r.tokens_out.toLocaleString("en-US")}</td>
                  <td className="num mono">{r.cost_usd === null ? `unknown (${r.cost_unknown})` : `$${r.cost_usd.toFixed(4)}`}</td>
                </tr>
              ))}
              <tr className="nohover set-total">
                <th scope="row" colSpan={2}>Total</th>
                <td className="num mono">{data.total_results.toLocaleString("en-US")}</td>
                <td className="num mono" colSpan={2}>{data.total_tokens.toLocaleString("en-US")} tokens</td>
                <td className="num mono">{data.total_cost_usd === null ? "unknown" : `$${data.total_cost_usd.toFixed(4)}`}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
      {data && data.by_model.some((r) => r.provider === "demo") && (
        <p className="ff-hint">Demo token counts are estimates (≈4 characters per token) and cost nothing.</p>
      )}
    </section>
  );
}

export function SettingsPage() {
  return (
    <AccessGate title="Settings" plate="09" purpose="Provider, model, temperature and step limits change how new runs behave, so they are kept behind the study's access code.">
      <SettingsContent />
    </AccessGate>
  );
}

function SettingsContent() {
  const { data, error, isPending } = useSettings();
  return (
    <div className="datapage settings" data-testid="settings-page">
      <header className="dp-header">
        <div>
          <PageTitle plate="09">Settings</PageTitle>
          <p className="dp-sub">
            Non-secret settings saved here override the server environment (<span className="mono">.env</span> locally).
            API keys stay in the environment only and are never shown.
          </p>
        </div>
      </header>
      {isPending && <p className="empty-body">Loading settings…</p>}
      {error && <p className="error-text" role="alert">{error.message}</p>}
      <div className="set-layout">
        <div className="set-main">{data && <SettingsForm key={JSON.stringify(data.values)} view={data} />}</div>
        <div className="set-side">
          <Usage />
        </div>
      </div>
    </div>
  );
}
