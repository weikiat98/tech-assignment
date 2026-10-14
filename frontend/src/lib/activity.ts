import { STAGES, currentStage, stageOf } from "./stages";
import type { AgentEvent } from "./types";

/**
 * Plain-language view of a run's events (todo.md CL8): the seven pipeline stages as one sentence each, and a
 * sentence per notable event for "Every action". Pure, so it is unit-tested on recorded events. The raw JSON
 * stays reachable from the UI ("Technical details").
 */

export interface ActivityLine {
  seq: number;
  stage: number;
  text: string;
  /** `note` lines (fallbacks, removed claims) are shown in amber; `error` in red. */
  tone: "normal" | "note" | "error";
  event: AgentEvent;
}

export interface StageSummary {
  stage: number;
  label: string;
  /** One sentence; empty until the stage has started. */
  text: string;
  done: boolean;
  tone: "normal" | "note";
}

const SOURCE_NAMES: Record<string, string> = {
  fetch_singstat: "SingStat",
  singstat_search_tables: "SingStat",
  fetch_datagov: "Data.gov.sg",
  datagov_search: "Data.gov.sg",
  fetch_mom_excel: "MOM",
  query_internal_db: "internal systems",
  web_search: "the web",
  fetch_web_page: "the web",
};

const RUNNING: readonly string[] = [
  "interpreting your question",
  "planning the work",
  "collecting data",
  "checking data quality",
  "analysing the data",
  "writing the report",
  "verifying every claim",
];

/** Thoughts carry the plan's task ids ("T2: ..."); readers don't need them. */
export function stripTaskId(text: string): string {
  return text.replace(/^T\d+:\s*/, "");
}

function quoted(v: unknown): string {
  return v ? `“${String(v)}”` : "";
}

function actionText(tool: string, input: Record<string, unknown>): string {
  switch (tool) {
    case "singstat_search_tables":
      return `Searched SingStat for ${quoted(input.query_text)}`.trim();
    case "singstat_get_metadata":
      return "Read the table's details";
    case "fetch_singstat": {
      const n = Array.isArray(input.series) ? input.series.length : 0;
      return `Downloaded ${n ? `${n} series` : "the table"} from SingStat`;
    }
    case "datagov_search":
      return `Searched Data.gov.sg for ${quoted(input.query)}`.trim();
    case "fetch_datagov":
      return `Downloaded ${input.title ? quoted(input.title) : "a dataset"} from Data.gov.sg`;
    case "fetch_mom_excel":
      return "Loaded MOM's employment workbook";
    case "list_internal_tables":
      return "Looked up the internal tables";
    case "query_internal_db":
      return "Queried the internal programme data";
    case "web_search":
      return `Searched the web for ${quoted(input.query)}`.trim();
    case "fetch_web_page":
      return "Read a web page";
    case "extract_web_data":
      return "Pulled figures out of a web page";
    case "list_datasets":
      return "Listed the datasets collected so far";
    case "list_series":
      return "Listed the series available";
    case "annualise":
      return "Converted quarterly figures to annual";
    case "describe":
      return "Read the start, end and peak levels";
    case "change":
      return "Measured the change over the period";
    case "cagr":
      return "Computed the compound annual growth rate";
    case "yoy":
      return "Computed year-on-year growth";
    case "trend":
      return "Fitted a linear trend";
    case "share":
      return "Worked out the share of the total";
    case "correlate":
      return "Tested the correlation between two series";
    case "anomalies":
      return "Checked for unusual years";
    case "forecast":
      return "Projected the trend forward";
    case "make_chart":
      return `Drew ${input.kind ? `a ${String(input.kind).replace("_", " ")}` : "a"} chart`;
    default:
      return `Used ${tool.replace(/_/g, " ")}`;
  }
}

/** One sentence for an event, or null when it only adds noise (facts and report chunks are counted instead). */
export function describeEvent(e: AgentEvent): Pick<ActivityLine, "text" | "tone"> | null {
  const c = e.content;
  switch (e.type) {
    case "thought":
      return c.text ? { text: stripTaskId(String(c.text)), tone: "normal" } : null;
    case "action":
      return { text: actionText(String(c.tool), (c.input ?? {}) as Record<string, unknown>), tone: "normal" };
    case "observation": {
      if (c.is_error) return { text: `A step failed (${String(c.result?.error ?? "unknown error").slice(0, 120)}); trying another way`, tone: "note" };
      if (c.result?.reused) return { text: "Reused data already downloaded earlier in this chat", tone: "normal" };
      return null;
    }
    case "handoff":
      return { text: `Handed the work to the ${c.to} agent`, tone: "normal" };
    case "intent":
      return { text: `Understood the question: ${c.reasoning || c.topic}`, tone: "normal" };
    case "plan":
      return { text: `Planned ${c.tasks?.length ?? 0} tasks`, tone: "normal" };
    case "fallback":
      return c.kind === "llm"
        ? { text: `The ${c.from} model was unavailable, so ${c.to} answered instead`, tone: "note" }
        : c.kind === "budget"
          ? { text: "The AI spending limit for this run was reached; the rest used the built-in fallback model", tone: "note" }
          : { text: `Used a saved copy of ${c.dataset ?? c.source ?? "a source"} (${c.reason ?? c.via ?? "live source unavailable"})`, tone: "note" };
    case "quality":
      return c.report
        ? { text: `Checked ${c.title}: quality score ${Number(c.report.score).toFixed(2)}`, tone: "normal" }
        : { text: String(c.message), tone: String(c.message).includes("DIVERGE") ? "note" : "normal" };
    case "verification":
      return c.passed
        ? { text: "Checked every claim against the data: all passed", tone: "normal" }
        : { text: `${c.failing?.length ?? 0} claim(s) failed the check; asking the writer to fix them`, tone: "note" };
    case "warning":
      return c.kind === "claims_removed"
        ? { text: `Removed ${c.count} claim(s) that could not be verified`, tone: "note" }
        : { text: String(c.message ?? c.kind ?? "Warning"), tone: "note" };
    case "clarification":
      return { text: `Asked you: ${c.question}`, tone: "normal" };
    case "error":
      return { text: String(c.message), tone: "error" };
    case "final":
      return { text: `Finished: ${c.status}`, tone: "normal" };
    case "status":
      if (c.state === "replanning") return { text: "Not enough data was found; planning again", tone: "note" };
      if (c.state === "clarified") return { text: `Got your clarification: ${c.answer}`, tone: "normal" };
      if (c.state === "writing") return { text: `Writing the report (draft ${c.attempt ?? 1})`, tone: "normal" };
      if (c.state === "cancelled") return { text: "Stopped", tone: "note" };
      return null;
    default:
      return null;
  }
}

/** Every described event, in order ("Every action"). */
export function activityLines(events: AgentEvent[]): ActivityLine[] {
  const lines: ActivityLine[] = [];
  for (const e of events) {
    const d = describeEvent(e);
    if (d) lines.push({ seq: e.seq, stage: Math.max(stageOf(e), 0), text: d.text, tone: d.tone, event: e });
  }
  return lines;
}

function sourcesUsed(events: AgentEvent[]): string[] {
  const names = new Set<string>();
  for (const e of events) {
    if (e.type === "action" && SOURCE_NAMES[e.content.tool] && e.content.tool.startsWith("fetch")) {
      names.add(SOURCE_NAMES[e.content.tool]);
    }
    if (e.type === "action" && e.content.tool === "query_internal_db") names.add("internal systems");
  }
  return [...names];
}

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** The seven stages, each as one sentence, from the events so far. */
export function stageSummaries(events: AgentEvent[], finished: boolean): StageSummary[] {
  const reached = currentStage(events);
  const of = (stage: number) => events.filter((e) => stageOf(e) === stage);
  const datasets = events.filter((e) => e.type === "quality" && e.content.report);
  const sources = sourcesUsed(events);
  const facts = events.filter((e) => e.type === "fact").length;
  const charts = events.filter((e) => e.type === "chart").length;
  const scores = datasets.map((e) => Number(e.content.report.score));
  const avg = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
  const drafts = Math.max(0, ...events.filter((e) => e.type === "report_chunk").map((e) => Number(e.content.attempt ?? 1)));
  const verdicts = events.filter((e) => e.type === "verification");
  const lastVerdict = verdicts[verdicts.length - 1]?.content;
  const removed = events.find((e) => e.type === "warning" && e.content.kind === "claims_removed");
  const intent = events.find((e) => e.type === "intent")?.content;
  const plan = [...events].reverse().find((e) => e.type === "plan")?.content;

  const text: string[] = [
    intent ? `Understood the question: ${intent.reasoning || intent.topic}` : "",
    plan ? `Planned ${plural(plan.tasks?.length ?? 0, "task")}` : "",
    datasets.length
      ? `Collected ${plural(datasets.length, "dataset")}${sources.length ? ` from ${sources.join(", ")}` : ""}`
      : of(2).length
        ? `Collecting data${sources.length ? ` from ${sources.join(", ")}` : ""}`
        : "",
    avg !== null ? `Checked data quality: average score ${avg.toFixed(2)}` : "",
    facts || charts ? `Computed ${plural(facts, "figure")} and drew ${plural(charts, "chart")}` : of(4).length ? "Analysing the data" : "",
    drafts ? `Drafted the report${drafts > 1 ? ` (${drafts} drafts)` : ""}` : "",
    lastVerdict
      ? removed
        ? `Verified every claim; removed ${removed.content.count} that could not be supported`
        : lastVerdict.passed
          ? `Verified every claim: all passed${verdicts.length > 1 ? ` after ${plural(verdicts.length - 1, "rewrite")}` : ""}`
          : "A claim failed verification; the writer is fixing it"
      : "",
  ];
  const noted = new Set<number>();
  for (const e of events) if (["fallback", "warning"].includes(e.type)) noted.add(Math.max(stageOf(e), 0));
  return STAGES.map((label, stage) => ({
    stage,
    label,
    text: text[stage],
    done: finished ? stage <= reached : stage < reached,
    tone: noted.has(stage) ? "note" : "normal",
  }));
}

export interface ActivityHeadline {
  /** While running: "Step 3 of 7: collecting data from SingStat". Done: "Researched in 7 steps · ...". */
  text: string;
  steps: number;
  sources: number;
  notes: number;
  seconds: number | null;
}

export function headline(events: AgentEvent[], finished: boolean): ActivityHeadline {
  const reached = currentStage(events);
  const sources = sourcesUsed(events);
  const notes = events.filter((e) => ["fallback", "warning"].includes(e.type)).length;
  const first = events[0]?.ts;
  const last = events[events.length - 1]?.ts;
  const seconds = first && last ? Math.max(0, Math.round((Date.parse(last) - Date.parse(first)) / 1000)) : null;
  const steps = Math.max(reached + 1, 0);
  if (!finished) {
    if (reached < 0) return { text: "Starting…", steps, sources: sources.length, notes, seconds };
    const where = reached === 2 && sources.length ? ` from ${sources[sources.length - 1]}` : "";
    return {
      text: `Step ${reached + 1} of ${STAGES.length}: ${RUNNING[reached]}${where}`,
      steps,
      sources: sources.length,
      notes,
      seconds,
    };
  }
  const parts = [
    `Researched in ${plural(steps, "step")}`,
    plural(sources.length, "data source"),
    ...(notes ? [plural(notes, "note")] : []),
    ...(seconds !== null ? [`${seconds} s`] : []),
  ];
  return { text: parts.join(" · "), steps, sources: sources.length, notes, seconds };
}
