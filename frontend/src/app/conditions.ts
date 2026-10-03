export type ConditionId = "C0" | "C1" | "C2" | "C3" | "C4";

export const LADDER_STEPS = ["Retrieval", "Tools", "Verify", "Guardrail"] as const;
export type LadderStep = (typeof LADDER_STEPS)[number];

export interface Condition {
  id: ConditionId;
  name: string;
  summary: string;
  ladder: Record<LadderStep, boolean>;
}

export const CONDITIONS: readonly Condition[] = [
  {
    id: "C0",
    name: "Bare LLM",
    summary: "No tools. The model answers from its own knowledge.",
    ladder: { Retrieval: false, Tools: false, Verify: false, Guardrail: false },
  },
  {
    id: "C1",
    name: "Retrieval",
    summary: "One SVTG search; answer from passages with citations.",
    ladder: { Retrieval: true, Tools: false, Verify: false, Guardrail: false },
  },
  {
    id: "C2",
    name: "Tools",
    summary: "ReAct loop, up to 6 steps: guidelines, drug safety, withdrawal, patient record.",
    ladder: { Retrieval: true, Tools: true, Verify: false, Guardrail: false },
  },
  {
    id: "C3",
    name: "Self-verify",
    summary: "C2, then each claim is checked against retrieved evidence and revised.",
    ladder: { Retrieval: true, Tools: true, Verify: true, Guardrail: false },
  },
  {
    id: "C4",
    name: "Guardrail",
    summary: "C3, then deterministic rules: banned drugs, red-flag escalation, notifiable disease.",
    ladder: { Retrieval: true, Tools: true, Verify: true, Guardrail: true },
  },
];
