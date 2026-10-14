import { describe, expect, it } from "vitest";
import { STAGES, currentStage, stageProgress } from "./stages";
import type { AgentEvent } from "./types";

let seq = 0;
const ev = (agent: string, type: string, content: Record<string, unknown> = {}): AgentEvent =>
  ({ run_id: "r", seq: ++seq, agent, type, content, tokens: 0, cost_usd: 0, ts: new Date().toISOString() }) as AgentEvent;

describe("stage progress", () => {
  it("is indeterminate before any stage event", () => {
    expect(currentStage([])).toBe(-1);
    expect(stageProgress([ev("system", "status")], false)).toBeNull();
  });

  it("follows the furthest stage reached and never goes backwards on a replan", () => {
    const events = [ev("coordinator", "intent"), ev("coordinator", "plan"), ev("extraction", "action"), ev("analytics", "chart")];
    expect(STAGES[currentStage(events)]).toBe("Analyse");
    const replanned = [...events, ev("coordinator", "plan")];
    expect(currentStage(replanned)).toBe(currentStage(events));
    expect(stageProgress(events, false)).toBe(Math.round((5 / STAGES.length) * 100));
  });

  it("is 100% when finished", () => {
    expect(stageProgress([], true)).toBe(100);
  });
});
