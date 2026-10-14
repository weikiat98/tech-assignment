import { describe, expect, it } from "vitest";
import { activityLines, describeEvent, headline, stageSummaries, stripTaskId } from "./activity";
import { STAGES } from "./stages";
import type { AgentEvent } from "./types";
// Events recorded from the sample queries on MockLLM (offline snapshots).
import recorded from "./fixtures/runs.json";

const main = recorded.main as AgentEvent[];
const why = recorded.why as AgentEvent[];

const ev = (type: string, content: Record<string, unknown>, agent = "extraction"): AgentEvent =>
  ({ run_id: "r", seq: 1, agent, type, content, tokens: 0, cost_usd: 0, ts: "2026-10-14T00:00:00Z" }) as AgentEvent;

describe("describeEvent", () => {
  it("names tools in plain language instead of showing calls and JSON", () => {
    expect(describeEvent(ev("action", { tool: "singstat_search_tables", input: { query_text: "employment by sector" } }))?.text).toBe(
      "Searched SingStat for “employment by sector”",
    );
    expect(describeEvent(ev("action", { tool: "fetch_singstat", input: { resource_id: "M1", series: ["3", "3.4"] } }))?.text).toBe(
      "Downloaded 2 series from SingStat",
    );
    expect(describeEvent(ev("action", { tool: "singstat_get_metadata", input: { resource_id: "M1" } }))?.text).toBe("Read the table's details");
    expect(describeEvent(ev("action", { tool: "make_chart", input: { kind: "yoy_bar" } }))?.text).toBe("Drew a yoy bar chart");
    expect(describeEvent(ev("action", { tool: "something_new", input: {} }))?.text).toBe("Used something new");
  });

  it("strips task ids from thoughts", () => {
    expect(stripTaskId("T2: load the MOM workbook")).toBe("load the MOM workbook");
    expect(describeEvent(ev("thought", { text: "T1: search SingStat" }))?.text).toBe("search SingStat");
  });

  it("turns fallbacks into amber notes and hides successful observations, facts and report chunks", () => {
    const note = describeEvent(ev("fallback", { kind: "llm", from: "openai", to: "gemini", task: "plan" }));
    expect(note).toEqual({ text: "The openai model was unavailable, so gemini answered instead", tone: "note" });
    expect(describeEvent(ev("fallback", { kind: "source", dataset: "singstat:M1", reason: "offline mode" }))?.tone).toBe("note");
    expect(describeEvent(ev("observation", { tool: "x", result: { ok: 1 }, is_error: false }))).toBeNull();
    expect(describeEvent(ev("observation", { tool: "x", result: { error: "boom" }, is_error: true }))?.tone).toBe("note");
    expect(describeEvent(ev("fact", { id: "F1" }))).toBeNull();
    expect(describeEvent(ev("report_chunk", { section: "title" }))).toBeNull();
  });

  it("states what quality checks found as a score sentence", () => {
    expect(describeEvent(ev("quality", { title: "Employment", report: { score: 0.93, issues: [] } }))?.text).toBe(
      "Checked Employment: quality score 0.93",
    );
  });
});

describe("recorded sample runs", () => {
  it("never leaks raw tool calls or JSON into the sentences", () => {
    for (const run of [main, why]) {
      for (const line of activityLines(run)) {
        expect(line.text).not.toMatch(/[{}]|\(\{|resource_id|_id"/);
        expect(line.text).not.toMatch(/^T\d+:/);
      }
    }
  });

  it("summarises all seven stages of a finished run", () => {
    const stages = stageSummaries(main, true);
    expect(stages.map((s) => s.label)).toEqual([...STAGES]);
    for (const s of stages) expect(s.text, `stage ${s.label}`).not.toBe("");
    expect(stages.every((s) => s.done)).toBe(true);
    expect(stages[2].text).toMatch(/^Collected \d+ datasets? from SingStat/);
    expect(stages[4].text).toMatch(/^Computed \d+ figures and drew \d+ charts$/);
    expect(stages[6].text).toMatch(/^Verified every claim: all passed/);
  });

  it("describes a running run by its furthest stage, counting rather than listing facts", () => {
    const upToExtraction = main.slice(0, main.findIndex((e) => e.type === "quality"));
    const h = headline(upToExtraction, false);
    expect(h.text).toMatch(/^Step 3 of 7: collecting data/);
    expect(headline([], false).text).toBe("Starting…");
    const stages = stageSummaries(upToExtraction, false);
    expect(stages[4].text).toBe("");
    expect(stages[2].done).toBe(false);
    expect(stages[2].text).toMatch(/^Collecting data/);
  });

  it("gives the finished headline with steps, sources, notes and time", () => {
    const h = headline(main, true);
    expect(h.text).toMatch(/^Researched in 7 steps · \d+ data sources?/);
    expect(h.steps).toBe(7);
    expect(h.notes).toBeGreaterThan(0); // offline snapshots are reported as notes
    expect(h.text).toMatch(/\d+ s$/);
  });

  it("covers the web-context run with a web source and keeps every line in a known stage", () => {
    expect(headline(why, true).text).toContain("data source");
    for (const line of activityLines(why)) expect(line.stage).toBeGreaterThanOrEqual(0);
    expect(activityLines(why).some((l) => /Searched the web/.test(l.text))).toBe(true);
  });
});
