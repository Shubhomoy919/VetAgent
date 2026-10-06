import type { Citation } from "../api/runs";
import { useSvtgPage } from "../api/runs";
import "./Sidenotes.css";

/** Superscript reference numbers placed after the answer text. */
export function SidenoteRefs({ citations, active, onToggle }: { citations: Citation[]; active: number | null; onToggle: (i: number) => void }) {
  return (
    <>
      {citations.map((c, i) => (
        <sup key={`${c.page}-${i}`} className="sn-ref-wrap">
          <button
            type="button"
            className="sn-ref"
            aria-expanded={active === i}
            aria-label={`Citation ${i + 1}: SVTG page ${c.page}`}
            onClick={() => onToggle(i)}
          >
            {i + 1}
          </button>
        </sup>
      ))}
    </>
  );
}

function Note({ n, c, active, onCite }: { n: number; c: Citation; active: boolean; onCite: (page: number) => void }) {
  const { data } = useSvtgPage(c.page);
  const text = data?.chunks[0]?.text ?? "";
  const excerpt = text.length > 150 ? `${text.slice(0, 150).trimEnd()}…` : text;
  return (
    <li className="sn" data-active={active || undefined}>
      <span className="sn-n mono" aria-hidden="true">
        {n}
      </span>
      <div className="sn-body">
        <button type="button" className="cite-chip mono" onClick={() => onCite(c.page as number)} title="Open the SVTG passage">
          SVTG p.{c.page}
          {data?.printed_page ? ` · printed ${data.printed_page}` : ""}
        </button>
        {excerpt && <p className="sn-text">{excerpt}</p>}
      </div>
    </li>
  );
}

/** Sidenote citations: on wide cards the cited SVTG passages sit in the margin with their page numbers;
 *  on narrow cards only the note whose number was clicked shows, as a popover. */
export function SidenoteList({ citations, active, onCite }: { citations: Citation[]; active: number | null; onCite: (page: number) => void }) {
  if (citations.length === 0) return null;
  return (
    <ol className="sidenotes" aria-label="Citations">
      {citations.map((c, i) => (
        <Note key={`${c.page}-${i}`} n={i + 1} c={c} active={active === i} onCite={onCite} />
      ))}
    </ol>
  );
}
