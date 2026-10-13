import { describe, expect, it } from "vitest";
import { STAGES, currentStage, stageProgress } from "./stages";
import { filterEvents } from "../components/AgentTimeline";
import { filterByStatus } from "../pages/History";
import type { AgentEvent, AnalysisSummary } from "./types";

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

describe("timeline filters", () => {
  const events = [
    ev("coordinator", "thought"),
    ev("extraction", "action"),
    ev("extraction", "fallback"),
    ev("analytics", "fact"),
    ev("writer", "report_chunk"),
    ev("system", "status"),
  ];
  const defaults = ["reasoning", "data", "alerts", "status"];

  it("hides facts and draft chunks by default", () => {
    expect(filterEvents(events, [], defaults).map((e) => e.type)).toEqual(["thought", "action", "fallback", "status"]);
  });

  it("filters by agent, keeping system events, and treats none selected as all", () => {
    expect(filterEvents(events, ["extraction"], defaults).map((e) => e.type)).toEqual(["action", "fallback", "status"]);
    expect(filterEvents(events, [], [...defaults, "facts"])).toHaveLength(events.length);
  });

  it("filters by kind", () => {
    expect(filterEvents(events, [], ["alerts"]).map((e) => e.type)).toEqual(["fallback"]);
  });
});

describe("history status filter", () => {
  const row = (status: string) => ({ id: status, status }) as AnalysisSummary;
  const rows = [row("completed"), row("failed"), row("queued"), row("running")];

  it("shows everything when nothing is selected", () => {
    expect(filterByStatus(rows, [])).toHaveLength(4);
  });

  it("counts queued runs as running", () => {
    expect(filterByStatus(rows, ["running"]).map((r) => r.status)).toEqual(["queued", "running"]);
    expect(filterByStatus(rows, ["failed", "completed"]).map((r) => r.status)).toEqual(["completed", "failed"]);
  });
});
