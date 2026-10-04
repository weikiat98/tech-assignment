import { useEffect, useRef, useState } from "react";
import type { AgentEvent } from "../lib/types";

const AGENT_COLORS: Record<string, string> = {
  coordinator: "bg-violet-600",
  extraction: "bg-sky-600",
  analytics: "bg-emerald-600",
  writer: "bg-amber-600",
  verifier: "bg-rose-600",
  system: "bg-slate-500",
};

const TYPE_LABEL: Record<string, string> = {
  thought: "Thought",
  action: "Action",
  observation: "Observation",
  handoff: "Hand-off",
  intent: "Intent",
  plan: "Plan",
  fallback: "Fallback",
  quality: "Quality",
  fact: "Fact",
  chart: "Chart",
  verification: "Verification",
  clarification: "Clarification",
  warning: "Warning",
  error: "Error",
  status: "Status",
  report_chunk: "Report",
  final: "Done",
};

function summary(e: AgentEvent): string {
  const c = e.content;
  switch (e.type) {
    case "thought":
      return c.text;
    case "action":
      return `${c.tool}(${JSON.stringify(c.input ?? {}).slice(0, 160)})`;
    case "observation":
      return c.is_error ? `Error: ${c.result?.error ?? ""}` : JSON.stringify(c.result).slice(0, 180);
    case "handoff":
      return `→ ${c.to}`;
    case "intent":
      return c.reasoning || c.topic;
    case "plan":
      return `${c.tasks?.length ?? 0} tasks · ${c.reasoning ?? ""}`;
    case "fallback":
      return c.kind === "llm" ? `LLM ${c.from} → ${c.to} (${c.task})` : `${c.dataset ?? c.source ?? c.kind}: ${c.reason ?? c.via ?? (c.errors ?? []).join("; ")}`;
    case "quality":
      return c.report ? `${c.title}: score ${c.report.score} · ${c.report.issues.length} issue(s)` : c.message;
    case "fact":
      return `${c.id} ${c.label}: ${c.display}`;
    case "chart":
      return `${c.id} ${c.title}`;
    case "verification":
      return `${c.passed ? "passed" : "failed"} · numeric ${(c.numeric_pass_rate * 100).toFixed(0)}% · attempt ${c.attempt}`;
    case "clarification":
      return c.question;
    case "warning":
      return c.message ?? `${c.kind}${c.url ? ` · ${c.url}` : ""}`;
    case "error":
      return c.message;
    case "report_chunk":
      return `${c.section}: ${String(c.text).slice(0, 140)}`;
    case "final":
      return `Finished: ${c.status}`;
    default:
      return c.state ? `${c.state}${c.summary ? ` · ${c.summary}` : ""}` : JSON.stringify(c).slice(0, 140);
  }
}

const HIDDEN_BY_DEFAULT = new Set(["fact", "report_chunk"]);

export default function AgentTimeline({ events, connected }: { events: AgentEvent[]; connected: boolean }) {
  const [showAll, setShowAll] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const visible = showAll ? events : events.filter((e) => !HIDDEN_BY_DEFAULT.has(e.type));

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [visible.length]);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-slate-300"}`} />
          {connected ? "live" : "offline"} · {events.length} events
        </span>
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> show facts
        </label>
      </div>
      <ol className="flex-1 space-y-1.5 overflow-y-auto pr-1">
        {visible.map((e) => {
          const alert = ["fallback", "warning", "error"].includes(e.type);
          return (
            <li
              key={e.seq}
              className={`cursor-pointer rounded-lg border px-2.5 py-1.5 text-xs ${
                alert ? "border-amber-300 bg-amber-50" : "border-slate-100 bg-white hover:border-slate-300"
              } ${e.type === "error" ? "border-red-300 bg-red-50" : ""}`}
              onClick={() => setOpen(open === e.seq ? null : e.seq)}
            >
              <div className="flex items-center gap-2">
                <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase text-white ${AGENT_COLORS[e.agent] ?? "bg-slate-500"}`}>
                  {e.agent}
                </span>
                <span className="font-medium text-slate-700">{TYPE_LABEL[e.type] ?? e.type}</span>
                {e.content.step && <span className="text-slate-400">step {e.content.step}</span>}
                <span className="ml-auto text-[10px] text-slate-400">{new Date(e.ts).toLocaleTimeString()}</span>
              </div>
              <p className="mt-1 break-words text-slate-600">{summary(e)}</p>
              {open === e.seq && (
                <pre className="mt-2 max-h-64 overflow-auto rounded bg-slate-900 p-2 text-[10px] text-slate-100">
                  {JSON.stringify(e.content, null, 2)}
                </pre>
              )}
            </li>
          );
        })}
        <div ref={bottom} />
      </ol>
    </div>
  );
}
