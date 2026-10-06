import { useState } from "react";
import { applyLedgerDense, readLedgerDense } from "../app/theme";

/** Dense / comfortable toggle for ledger tables (remembered). */
export function LedgerToggle() {
  const [dense, setDense] = useState(readLedgerDense);
  return (
    <button
      type="button"
      className="btn ledger-toggle"
      aria-pressed={dense}
      title="Ledger line spacing"
      onClick={() => {
        applyLedgerDense(!dense);
        setDense(!dense);
      }}
    >
      {dense ? "Dense ledger" : "Comfortable ledger"}
    </button>
  );
}
