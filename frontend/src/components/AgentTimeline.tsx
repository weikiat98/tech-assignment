import { useEffect, useMemo, useRef, useState } from "react";
import type { AgentEvent } from "../lib/types";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
  ScrollArea,
  ToggleGroup,
  ToggleGroupItem,
  cn,
} from "./ui";

const AGENT_COLORS: Record<string, string> = {
  coordinator: "bg-agent-coordinator",
  extraction: "bg-agent-extraction",
  analytics: "bg-agent-analytics",
  writer: "bg-agent-writer",
  verifier: "bg-agent-verifier",
  system: "bg-agent-system",
};

const AGENTS = ["coordinator", "extraction", "analytics", "writer", "verifier"] as const;

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

/** Event kinds the filter groups: reasoning, data, alerts, status; "facts" are the high-volume extras. */
export const KINDS = {
  reasoning: ["thought", "action", "observation", "handoff", "intent", "plan"],
  data: ["quality", "chart"],
  alerts: ["fallback", "warning", "error"],
  status: ["status", "verification", "clarification", "final"],
  facts: ["fact", "report_chunk"],
} as const;
type Kind = keyof typeof KINDS;
const KIND_LABEL: Record<Kind, string> = {
  reasoning: "Reasoning",
  data: "Data",
  alerts: "Alerts",
  status: "Status",
  facts: "Facts & draft",
};
const DEFAULT_KINDS: Kind[] = ["reasoning", "data", "alerts", "status"];

function kindOf(type: string): Kind | null {
  for (const k of Object.keys(KINDS) as Kind[]) if ((KINDS[k] as readonly string[]).includes(type)) return k;
  return null;
}

/** Pure filter, exported for tests. An empty agent set means "all agents". */
export function filterEvents(events: AgentEvent[], agents: string[], kinds: string[]): AgentEvent[] {
  return events.filter((e) => {
    const kind = kindOf(e.type);
    if (kind && !kinds.includes(kind)) return false;
    return agents.length === 0 || agents.includes(e.agent) || e.agent === "system";
  });
}

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

export default function AgentTimeline({ events, connected }: { events: AgentEvent[]; connected: boolean }) {
  const [agents, setAgents] = useState<string[]>([]);
  const [kinds, setKinds] = useState<string[]>(DEFAULT_KINDS);
  const bottom = useRef<HTMLDivElement>(null);
  const visible = useMemo(() => filterEvents(events, agents, kinds), [events, agents, kinds]);

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }, [visible.length]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex items-center justify-between text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-slate-300"}`} />
          {connected ? "live" : "offline"} · {visible.length === events.length ? events.length : `${visible.length} of ${events.length}`} events
        </span>
      </div>
      <div className="mb-2 space-y-1.5">
        <ToggleGroup
          type="multiple"
          value={agents}
          onValueChange={setAgents}
          aria-label="Filter by agent (none selected shows all)"
          className="flex flex-wrap gap-1"
        >
          {AGENTS.map((a) => (
            <ToggleGroupItem key={a} value={a} className="capitalize">
              {a}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <ToggleGroup type="multiple" value={kinds} onValueChange={setKinds} aria-label="Filter by event kind" className="flex flex-wrap gap-1">
          {(Object.keys(KINDS) as Kind[]).map((k) => (
            <ToggleGroupItem key={k} value={k}>
              {KIND_LABEL[k]}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      <ScrollArea className="min-h-0 flex-1" viewportClassName="pr-2">
        <ol className="space-y-1.5">
          {visible.length === 0 && (
            <li className="py-8 text-center text-xs text-slate-400">
              {events.length === 0 ? "Waiting for the first agent event…" : "No events match these filters."}
            </li>
          )}
          {visible.map((e) => {
            const alert = ["fallback", "warning", "error"].includes(e.type);
            return (
              <li key={e.seq}>
                <Collapsible
                  className={cn(
                    "rounded-lg border text-xs",
                    alert ? "border-amber-300 bg-amber-50" : "border-line bg-surface hover:border-line-strong",
                    e.type === "error" && "border-red-300 bg-red-50",
                  )}
                >
                  <CollapsibleTrigger className="block w-full px-2.5 py-1.5">
                    <div className="flex items-center gap-2">
                      <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase text-white", AGENT_COLORS[e.agent] ?? "bg-agent-system")}>
                        {e.agent}
                      </span>
                      <span className="font-medium text-slate-700">{TYPE_LABEL[e.type] ?? e.type}</span>
                      {e.content.step && <span className="text-slate-400">step {e.content.step}</span>}
                      <span className="ml-auto text-[10px] text-slate-400">{new Date(e.ts).toLocaleTimeString()}</span>
                    </div>
                    <p className="mt-1 break-words text-slate-600">{summary(e)}</p>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <pre className="mx-2.5 mb-2 max-h-64 overflow-auto rounded bg-slate-900 p-2 text-[10px] text-slate-100">
                      {JSON.stringify(e.content, null, 2)}
                    </pre>
                  </CollapsibleContent>
                </Collapsible>
              </li>
            );
          })}
          <div ref={bottom} />
        </ol>
      </ScrollArea>
    </div>
  );
}
