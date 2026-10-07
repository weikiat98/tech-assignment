import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useRunEvents } from "../lib/useRunEvents";
import AgentTimeline from "../components/AgentTimeline";
import ClarificationCard from "../components/ClarificationCard";
import { ChartsPanel, DataPanel, InsightsPanel, PlanPanel, ReportPanel } from "../components/ResultPanels";
import { StatusBadge } from "../components/ui";

const TABS = ["Insights", "Charts", "Data & quality", "Report", "Plan"] as const;
type Tab = (typeof TABS)[number];
const ACTIVE = new Set(["queued", "running", "awaiting_input"]);

export default function RunView() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("Insights");
  const autoSwitched = useRef(false);
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

  const cancel = useMutation({ mutationFn: () => api.cancel(id!) });
  const clarification = [...events].reverse().find((e) => e.type === "clarification")?.content;
  const result = analysis?.result ?? null;
  const cost = result?.total_cost_usd ?? events.reduce((s, e) => s + (e.cost_usd || 0), 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-slate-500">Research question</p>
          <h1 className="text-lg font-semibold">{analysis?.query ?? "…"}</h1>
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
            <button onClick={() => cancel.mutate()} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs">
              Cancel
            </button>
          )}
          {result &&
            (["pdf", "md", "json", "csv"] as const).map((f) => (
              <a
                key={f}
                href={api.exportUrl(id!, f)}
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium uppercase hover:border-brand-500"
              >
                {f}
              </a>
            ))}
        </div>
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
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">Run failed: {analysis.error}</div>
      )}

      <div className="grid gap-4 lg:grid-cols-[420px_1fr]">
        <section className="flex h-[calc(100vh-220px)] min-h-[420px] flex-col rounded-xl border border-slate-200 bg-slate-50 p-3">
          <h2 className="mb-2 text-sm font-semibold text-slate-800">Agent activity</h2>
          <AgentTimeline events={events} connected={connected} />
        </section>
        <section className="min-w-0 rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex gap-1 overflow-x-auto border-b border-slate-100 px-3 pt-2">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm ${
                  tab === t ? "border-brand-600 font-medium text-brand-700" : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="p-4">
            {tab === "Insights" && <InsightsPanel result={result} />}
            {tab === "Charts" && <ChartsPanel result={result} events={events} />}
            {tab === "Data & quality" && <DataPanel result={result} events={events} />}
            {tab === "Report" && <ReportPanel result={result} events={events} />}
            {tab === "Plan" && <PlanPanel events={events} />}
          </div>
        </section>
      </div>
    </div>
  );
}
