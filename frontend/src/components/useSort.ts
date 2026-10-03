import { useMemo, useState } from "react";

export type SortDir = "asc" | "desc";
type Value = string | number | boolean | null;

/** Client-side sort state for a table. Nulls always sort last. */
export function useSort<T, K extends string>(rows: T[], get: Record<K, (r: T) => Value>, initial: K) {
  const [key, setKey] = useState<K>(initial);
  const [dir, setDir] = useState<SortDir>("asc");
  const sorted = useMemo(() => {
    const f = get[key];
    const copy = [...rows];
    copy.sort((a, b) => {
      const x = f(a);
      const y = f(b);
      if (x === y) return 0;
      if (x === null) return 1;
      if (y === null) return -1;
      const c =
        typeof x === "number" && typeof y === "number"
          ? x - y
          : String(x).localeCompare(String(y), undefined, { numeric: true });
      return dir === "asc" ? c : -c;
    });
    return copy;
  }, [rows, get, key, dir]);
  const toggle = (k: string) => {
    const kk = k as K;
    if (kk === key) setDir(dir === "asc" ? "desc" : "asc");
    else {
      setKey(kk);
      setDir("asc");
    }
  };
  return { sorted, key, dir, toggle };
}
