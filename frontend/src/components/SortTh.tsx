import type { SortDir } from "./useSort";

/** Sortable column header: a button inside <th> with aria-sort. */
export function SortTh({ label, k, sortKey, dir, onSort, className }: {
  label: string;
  k: string;
  sortKey: string;
  dir: SortDir;
  onSort: (k: string) => void;
  className?: string;
}) {
  const active = k === sortKey;
  return (
    <th scope="col" aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"} className={className}>
      <button type="button" className="th-sort" onClick={() => onSort(k)}>
        {label}
        <span className="th-arrow" aria-hidden="true">
          {active ? (dir === "asc" ? "↑" : "↓") : "↕"}
        </span>
      </button>
    </th>
  );
}
