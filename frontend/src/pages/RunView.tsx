import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useRunEvents } from "../lib/useRunEvents";
import { STAGES, currentStage, stageProgress } from "../lib/stages";
import AgentTimeline from "../components/AgentTimeline";
import ClarificationCard from "../components/ClarificationCard";
import { ChartsPanel, DataPanel, InsightsPanel, PlanPanel, ReportPanel } from "../components/ResultPanels";
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  StageProgress,
  StatusBadge,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  cn,
  useToast,
} from "../components/ui";

const TABS = ["Insights", "Charts", "Data & quality", "Report", "Plan"] as const;
type Tab = (typeof TABS)[number];
const ACTIVE = new Set(["queued", "running", "awaiting_input"]);
const EXPORTS = [
  { format: "pdf", label: "PDF report" },
  { format: "md", label: "Markdown" },
  { format: "json", label: "JSON (facts + report)" },
  { format: "csv", label: "CSV (datasets, zip)" },
] as const;

export default function RunView() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("Insights");
  // Below `lg` the activity timeline and the results are two top-level panes instead of side by side.
  const [pane, setPane] = useState<"results" | "activity">("results");
  const autoSwitched = useRef(false);
  const mountedAt = useRef(Date.now());
  const toasted = useRef(0);
  const { data: analysis } = useQuery({
    queryKey: ["analysis", id],
    queryFn: () => api.getAnalysis(id!),
    enabled: Boolean(id),
    refetchInterval: (q) => (q.state.data && ACTIVE.has(q.state.data.status) ? 4000 : false),
  });
  const active = !analysis || ACTIVE.has(analysis.status);
  const { events, connected } = useRunEvents(id, true);
  const last = events[events.length - 1];

  // Refresh the stored result as soon as the run reports completion or asks for input.
  useEffect(() => {
    if (last && ["final", "clarification", "error"].includes(last.type)) {
      qc.invalidateQueries({ queryKey: ["analysis", id] });
    }
  }, [last, id, qc]);
  useEffect(() => {
    // While a run is live, jump to Charts once when the first chart arrives...
    if (last?.type === "chart" && tab === "Insights" && !autoSwitched.current) {
      autoSwitched.current = true;
      setTab("Charts");
    }
  }, [last, tab]);
  useEffect(() => {
    // ...and back to Insights once when the result lands. Never override a tab the user picked.
    if (analysis?.result && autoSwitched.current) {
      autoSwitched.current = false;
      setTab((t) => (t === "Charts" ? "Insights" : t));
    }
  }, [analysis?.result]);

  // Toasts for notable live events. Events older than this page load are a replay of history: skip them.
  useEffect(() => {
    for (const e of events) {
      if (e.seq <= toasted.current) continue;
      toasted.current = e.seq;
      if (Date.parse(e.ts) < mountedAt.current - 5000) continue;
      const c = e.content;
      if (e.type === "fallback") {
        toast({
          title: c.kind === "llm" ? `LLM fallback: ${c.from} → ${c.to}` : "Source fallback",
          description: c.kind === "llm" ? c.task : String(c.dataset ?? c.source ?? c.kind ?? ""),
          tone: "warning",
        });
      } else if (e.type === "verification" && c.passed === false) {
        toast({ title: "Draft failed verification", description: `Rewriting (attempt ${c.attempt})`, tone: "warning" });
      } else if (e.type === "error") {
        toast({ title: "Run error", description: String(c.message ?? ""), tone: "error" });
      } else if (e.type === "final") {
        toast({ title: `Analysis ${c.status}`, tone: c.status === "completed" ? "success" : "warning" });
      }
    }
  }, [events, toast]);

  const cancel = useMutation({
    mutationFn: () => api.cancel(id!),
    onSuccess: () => toast({ title: "Cancelling the run…" }),
    onError: (e) => toast({ title: "Could not cancel the run", description: (e as Error).message, tone: "error" }),
  });
  const clarification = [...events].reverse().find((e) => e.type === "clarification")?.content;
  const result = analysis?.result ?? null;
  const cost = result?.total_cost_usd ?? events.reduce((s, e) => s + (e.cost_usd || 0), 0);
  const stageIdx = currentStage(events);
  const finished = Boolean(analysis && !ACTIVE.has(analysis.status));
  const progress = stageProgress(events, finished);
  const stageLabel = finished
    ? "Run finished"
    : stageIdx < 0
      ? analysis?.status === "queued" || !analysis ? "Queued" : "Starting"
      : `Stage ${stageIdx + 1} of ${STAGES.length}: ${STAGES[stageIdx]}`;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-slate-500">Research question</p>
          <h1 className="break-words text-lg font-semibold">{analysis?.query ?? "…"}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-500">
            {analysis && <StatusBadge status={analysis.status} />}
            <span>LLM: {result?.llm_providers_used.join(", ") || "…"}</span>
            <span>cost ${cost.toFixed(4)}</span>
            {result?.trace_url && (
              <a href={result.trace_url} target="_blank" rel="noreferrer" className="text-brand-700 underline">
                Open trace (Langfuse)
              </a>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {active && analysis?.status === "running" && (
            <Button size="sm" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
              Cancel
            </Button>
          )}
          {result && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm">
                  Export <span aria-hidden>▾</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                {EXPORTS.map((x) => (
                  <DropdownMenuItem key={x.format} asChild onSelect={() => toast({ title: `Export started: ${x.label}` })}>
                    <a href={api.exportUrl(id!, x.format)}>{x.label}</a>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>

      <div>
        <div className="mb-1 flex items-center justify-between text-xs text-slate-500" aria-live="polite">
          <span>{stageLabel}</span>
          {!finished && <span>{progress === null ? "" : `${progress}%`}</span>}
        </div>
        <StageProgress value={progress} label="Analysis progress" />
      </div>

      {analysis?.status === "awaiting_input" && clarification && (
        <ClarificationCard
          runId={id!}
          question={clarification.question}
          suggestions={clarification.suggestions ?? []}
          onAnswered={() => qc.invalidateQueries({ queryKey: ["analysis", id] })}
        />
      )}
      {analysis?.status === "failed" && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          Run failed: {analysis.error}
        </div>
      )}

      <Tabs value={pane} onValueChange={(v) => setPane(v as typeof pane)} className="lg:hidden">
        <TabsList aria-label="Switch between results and agent activity" className="rounded-xl border border-line bg-surface px-2 pb-0">
          <TabsTrigger value="results">Results</TabsTrigger>
          <TabsTrigger value="activity">Agent activity ({events.length})</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="grid gap-4 lg:grid-cols-[420px_1fr]">
        <section
          aria-label="Agent activity"
          className={cn(
            "h-[calc(100vh-260px)] min-h-[420px] flex-col rounded-xl border border-line bg-surface-sunken p-3 lg:flex",
            pane === "activity" ? "flex" : "hidden",
          )}
        >
          <h2 className="mb-2 text-sm font-semibold text-slate-800">Agent activity</h2>
          <div className="min-h-0 flex-1">
            <AgentTimeline events={events} connected={connected} />
          </div>
        </section>
        <section
          aria-label="Results"
          className={cn("min-w-0 rounded-xl border border-line bg-surface shadow-sm lg:block", pane === "results" ? "block" : "hidden")}
        >
          <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
            <TabsList aria-label="Analysis results">
              {TABS.map((t) => (
                <TabsTrigger key={t} value={t}>
                  {t}
                </TabsTrigger>
              ))}
            </TabsList>
            <div className="p-4">
              <TabsContent value="Insights">
                <InsightsPanel result={result} />
              </TabsContent>
              <TabsContent value="Charts">
                <ChartsPanel result={result} events={events} />
              </TabsContent>
              <TabsContent value="Data & quality">
                <DataPanel result={result} events={events} />
              </TabsContent>
              <TabsContent value="Report">
                <ReportPanel result={result} events={events} />
              </TabsContent>
              <TabsContent value="Plan">
                <PlanPanel events={events} />
              </TabsContent>
            </div>
          </Tabs>
        </section>
      </div>
    </div>
  );
}
