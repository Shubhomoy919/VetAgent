/* Labelled form controls with inline error messages (aria-invalid + aria-describedby). */
import { useId, type ReactNode } from "react";
import "./form.css";

interface Base {
  label: string;
  error?: string | undefined;
  hint?: string | undefined;
  span?: 1 | 2 | undefined;
}

function Wrap({ id, label, error, hint, span, children }: Base & { id: string; children: ReactNode }) {
  return (
    <div className="ff" data-span={span ?? 1} data-invalid={Boolean(error)}>
      <label htmlFor={id} className="ff-label">
        {label}
      </label>
      {children}
      {error ? (
        <span id={`${id}-err`} className="ff-error" role="alert">
          {error}
        </span>
      ) : hint ? (
        <span id={`${id}-hint`} className="ff-hint">
          {hint}
        </span>
      ) : null}
    </div>
  );
}

function described(id: string, error?: string, hint?: string): string | undefined {
  if (error) return `${id}-err`;
  if (hint) return `${id}-hint`;
  return undefined;
}

export function TextField({ label, value, onChange, error, hint, span, mono, type = "text", name }: Base & {
  value: string; onChange: (v: string) => void; mono?: boolean; type?: "text" | "number" | "date"; name: string;
}) {
  const id = useId();
  return (
    <Wrap id={id} label={label} error={error} hint={hint} span={span}>
      <input
        id={id}
        name={name}
        className={`ff-input${mono ? " mono" : ""}`}
        type={type}
        step={type === "number" ? "any" : undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={described(id, error, hint)}
      />
    </Wrap>
  );
}

export function TextArea({ label, value, onChange, error, hint, span = 2, rows = 3, name }: Base & {
  value: string; onChange: (v: string) => void; rows?: number; name: string;
}) {
  const id = useId();
  return (
    <Wrap id={id} label={label} error={error} hint={hint} span={span}>
      <textarea
        id={id}
        name={name}
        className="ff-input ff-textarea"
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={described(id, error, hint)}
      />
    </Wrap>
  );
}

export function SelectField({ label, value, onChange, options, error, hint, span, name }: Base & {
  value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; name: string;
}) {
  const id = useId();
  return (
    <Wrap id={id} label={label} error={error} hint={hint} span={span}>
      <select
        id={id}
        name={name}
        className="ff-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={described(id, error, hint)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Wrap>
  );
}

export function CheckField({ label, checked, onChange, error, name }: {
  label: string; checked: boolean; onChange: (v: boolean) => void; error?: string | undefined; name: string;
}) {
  const id = useId();
  return (
    <div className="ff ff-check" data-invalid={Boolean(error)}>
      <label htmlFor={id} className="toggle">
        <input id={id} name={name} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        {label}
      </label>
      {error && (
        <span className="ff-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

export function FormSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="fs">
      <legend className="fs-legend">{title}</legend>
      <div className="fs-grid">{children}</div>
    </fieldset>
  );
}

export function ErrorSummary({ messages }: { messages: string[] }) {
  if (messages.length === 0) return null;
  return (
    <div className="err-summary" role="alert" data-testid="error-summary">
      <span className="eyebrow">Fix before saving</span>
      <ul>
        {messages.map((m) => (
          <li key={m}>{m}</li>
        ))}
      </ul>
    </div>
  );
}
