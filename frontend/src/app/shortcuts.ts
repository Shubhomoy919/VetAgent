/** Keyboard shortcuts shown in the "?" sheet. Keep in sync with the handlers. */
export const SHORTCUTS: { group: string; items: [string, string][] }[] = [
  { group: "Anywhere", items: [["Ctrl K", "Command palette"], ["?", "This list"], ["Esc", "Close drawer or dialog"]] },
  {
    group: "Bench",
    items: [
      ["J / K", "Next / previous case"],
      ["X", "Select case for a batch run"],
      ["R", "Run this case"],
      ["Shift R", "Force re-run (ignore cache)"],
      ["1 – 5", "Jump to condition C0–C4"],
      ["G", "Reveal / hide gold answer"],
    ],
  },
  { group: "Review", items: [["1", "Acceptable"], ["2", "Unacceptable"], ["N", "Not sure"], ["J / K", "Next / previous answer"]] },
];
