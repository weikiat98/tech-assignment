import type { AgentEvent } from "./types";

export const STAGES = ["Interpret", "Plan", "Extract", "Quality", "Analyse", "Write", "Verify"] as const;

export function stageOf(e: AgentEvent): number {
  if (e.type === "verification" || e.agent === "verifier") return 6;
  if (e.type === "report_chunk" || e.agent === "writer") return 5;
  if (e.agent === "analytics" || e.type === "chart" || e.type === "fact") return 4;
  if (e.type === "quality") return 3;
  if (e.agent === "extraction") return 2;
  if (e.type === "plan") return 1;
  if (e.type === "intent") return 0;
  return -1;
}

/** Furthest pipeline stage reached so far (a replan or rewrite never moves the bar backwards); -1 if none. */
export function currentStage(events: AgentEvent[]): number {
  return events.reduce((max, e) => Math.max(max, stageOf(e)), -1);
}

/** Progress percent for the run header, or null (indeterminate) before the first stage event. */
export function stageProgress(events: AgentEvent[], finished: boolean): number | null {
  if (finished) return 100;
  const idx = currentStage(events);
  return idx < 0 ? null : Math.round(((idx + 1) / STAGES.length) * 100);
}
