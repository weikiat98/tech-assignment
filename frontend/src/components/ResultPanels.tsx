import { lazy, Suspense, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AgentEvent, AnalysisResult, Chart, Claim, DatasetSummary, Fact } from "../lib/types";

/** Full dataset summary once the run has finished; only key/title/quality while it is still running. */
type DatasetView = Pick<DatasetSummary, "key" | "title" | "quality"> & Partial<DatasetSummary>;
type PlanTask = NonNullable<AnalysisResult["plan"]>["tasks"][number];

// Plotly is ~1 MB: load it only when a chart is first shown, not with the app shell.
const PlotlyChart = lazy(() => import("./PlotlyChart"));
import { ScoreBar, TierBadge } from "./ui";

/* ---------- Report ---------- */

export function ReportPanel({ result, events }: { result: AnalysisResult | null; events: AgentEvent[] }) {
  if (result?.markdown) {
    return (
      <div className="prose-report">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.markdown}</ReactMarkdown>
      </div>
    );
  }
  const chunks = events.filter((e) => e.type === "report_chunk");
  const lastAttempt = Math.max(0, ...chunks.map((c) => c.content.attempt ?? 1));
  const current = chunks.filter((c) => (c.content.attempt ?? 1) === lastAttempt);
  if (!current.length) return <Empty text="The report will stream here once the writer starts." />;
  return (
    <div className="prose-report">
      <p className="text-xs text-amber-700">Draft {lastAttempt} - awaiting verification…</p>
      {current.map((c) =>
        c.content.section === "title" ? (
          <h1 key={c.seq}>{c.content.text}</h1>
        ) : c.content.section === "executive_summary" ? (
          <p key={c.seq}>{c.content.text}</p>
        ) : (
          <ul key={c.seq}>
            <li>{c.content.text}</li>
          </ul>
        ),
      )}
    </div>
  );
}

/* ---------- Insights ---------- */

function FactChip({ fact }: { fact: Fact | undefined; id: string }) {
  if (!fact) return null;
  return (
    <span className="group relative ml-1 inline-block cursor-help rounded bg-brand-50 px-1 text-[11px] font-medium text-brand-700 ring-1 ring-brand-100">
      {fact.id}
      <span className="pointer-events-none absolute bottom-full left-0 z-10 mb-1 hidden w-72 rounded-lg bg-slate-900 p-2 text-[11px] font-normal text-white shadow-lg group-hover:block">
        <b>{fact.label}</b>
        <br />
        {fact.display} · method: {fact.method}
        <br />
        source: {fact.source_keys.join(", ")}
        {fact.derived && <><br /><i>derived by this platform</i></>}
      </span>
    </span>
  );
}

function ClaimList({ claims, facts }: { claims: Claim[]; facts: Map<string, Fact> }) {
  return (
    <ul className="space-y-2">
      {claims.map((c, i) => (
        <li key={i} className="rounded-lg border border-slate-100 bg-slate-50/60 p-3 text-sm leading-relaxed">
          {c.text}
          {c.fact_ids.map((id) => (
            <FactChip key={id} id={id} fact={facts.get(id)} />
          ))}
        </li>
      ))}
    </ul>
  );
}

export function InsightsPanel({ result }: { result: AnalysisResult | null }) {
  if (!result?.report) return <Empty text="Insights appear when the report has been verified." />;
  const facts = new Map(result.facts.map((f) => [f.id, f]));
  const v = result.verification;
  return (
    <div className="space-y-5">
      {v && (
        <div className={`flex flex-wrap items-center gap-4 rounded-lg p-3 text-xs ${v.passed ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800"}`}>
          <b>{v.passed ? "✓ Verified" : "⚠ Verified with removals"}</b>
          <span>numeric checks {(v.numeric_pass_rate * 100).toFixed(0)}%</span>
          <span>citations {(v.citation_pass_rate * 100).toFixed(0)}%</span>
          <span>entities {(v.entity_pass_rate * 100).toFixed(0)}%</span>
          <span>drafts: {v.attempt}</span>
        </div>
      )}
      <Section title="Executive summary">
        <p className="text-sm leading-relaxed">{result.report.executive_summary}</p>
      </Section>
      <Section title="Key findings">
        <ClaimList claims={result.report.key_findings} facts={facts} />
      </Section>
      {result.report.sector_analysis.length > 0 && (
        <Section title="Sector analysis">
          <ClaimList claims={result.report.sector_analysis} facts={facts} />
        </Section>
      )}
      {result.report.policy_implications.length > 0 && (
        <Section title="Policy implications">
          <ClaimList claims={result.report.policy_implications} facts={facts} />
        </Section>
      )}
      {result.context_notes.length > 0 && (
        <Section title="Context from the web">
          <ul className="space-y-2">
            {result.context_notes.map((n) => (
              <li key={n.url} className="rounded-lg border border-slate-100 p-3 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <a href={n.url} target="_blank" rel="noreferrer" className="font-medium text-brand-700 underline">
                    {n.title}
                  </a>
                  <TierBadge tier={n.trust_tier} />
                  {n.injection_flagged && <span className="rounded bg-red-50 px-1.5 text-red-700 ring-1 ring-red-200">injection text removed</span>}
                </div>
                <p className="mt-1 text-slate-600">“{n.excerpt.slice(0, 280)}…”</p>
              </li>
            ))}
          </ul>
        </Section>
      )}
      {result.report.limitations.length > 0 && (
        <Section title="Limitations">
          <ul className="list-disc space-y-1 pl-5 text-xs text-slate-600">
            {result.report.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

/* ---------- Charts ---------- */

export function ChartsPanel({ result, events }: { result: AnalysisResult | null; events: AgentEvent[] }) {
  const charts = result?.charts ?? events.filter((e) => e.type === "chart").map((e) => e.content as Chart);
  if (!charts.length) return <Empty text="Charts appear as the analytics agent creates them." />;
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {charts.map((c) => (
        <div key={c.id} className="rounded-lg border border-slate-100 p-2">
          <Suspense fallback={<div className="h-[340px] animate-pulse rounded bg-slate-50" />}>
            <PlotlyChart chart={c} />
          </Suspense>
          <p className="px-2 pb-1 text-[11px] text-slate-500">Source: {c.source_keys.join(", ")}</p>
        </div>
      ))}
    </div>
  );
}

/* ---------- Data & quality ---------- */

export function DataPanel({ result, events }: { result: AnalysisResult | null; events: AgentEvent[] }) {
  const datasets =
    result?.datasets ??
    events
      .filter((e) => e.type === "quality" && e.content.report)
      .map((e): DatasetView => ({ key: e.content.dataset, title: e.content.title, quality: e.content.report }));
  const cross = events.filter((e) => e.type === "quality" && e.content.dataset === "cross-source");
  if (!datasets.length) return <Empty text="Datasets appear as the extraction agent fetches them." />;
  return (
    <div className="space-y-3">
      {datasets.map((d: DatasetView) => (
        <div key={d.key} className="rounded-lg border border-slate-200 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <code className="rounded bg-slate-100 px-1.5 text-xs">{d.key}</code>
            <span className="text-sm font-medium">{d.title}</span>
            {d.trust_tier && <TierBadge tier={d.trust_tier} />}
            {d.is_fallback && <span className="rounded bg-amber-100 px-1.5 text-[11px] text-amber-800">fallback</span>}
            <span className="ml-auto">{d.quality && <ScoreBar score={d.quality.score} />}</span>
          </div>
          {d.agency && (
            <p className="mt-1 text-xs text-slate-500">
              {d.agency} · {d.frequency} · {d.period_range?.join("–")} · {d.row_count} rows ·{" "}
              {d.url && (
                <a className="text-brand-700 underline" href={d.url} target="_blank" rel="noreferrer">
                  source
                </a>
              )}
            </p>
          )}
          {d.fallback_reason && <p className="mt-1 text-xs text-amber-700">{d.fallback_reason}</p>}
          {d.quality && (
            <div className="mt-2 grid gap-2 text-xs md:grid-cols-2">
              <div>
                <p className="font-medium text-slate-700">Checks</p>
                <ul className="mt-1 space-y-0.5">
                  {d.quality.issues.length === 0 && <li className="text-emerald-700">No issues found</li>}
                  {d.quality.issues.map((i, idx) => (
                    <li key={idx} className={i.severity === "error" ? "text-red-700" : i.severity === "warning" ? "text-amber-700" : "text-slate-500"}>
                      [{i.check}] {i.message.slice(0, 220)}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="font-medium text-slate-700">Cleaning actions</p>
                <ul className="mt-1 space-y-0.5 text-slate-600">
                  {d.quality.actions.length === 0 && <li>None needed</li>}
                  {d.quality.actions.map((a: string, idx: number) => (
                    <li key={idx}>{a}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      ))}
      {cross.length > 0 && (
        <div className="rounded-lg border border-slate-200 p-3 text-xs">
          <p className="font-medium text-slate-700">Cross-source consistency</p>
          <ul className="mt-1 space-y-0.5">
            {cross.map((e) => (
              <li key={e.seq} className={String(e.content.message).includes("DIVERGE") ? "text-amber-700" : "text-slate-600"}>
                {e.content.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ---------- Plan ---------- */

export function PlanPanel({ events }: { events: AgentEvent[] }) {
  const intent = [...events].reverse().find((e) => e.type === "intent")?.content;
  const plan = [...events].reverse().find((e) => e.type === "plan")?.content;
  if (!intent && !plan) return <Empty text="The coordinator's interpretation and plan appear here." />;
  return (
    <div className="space-y-4 text-sm">
      {intent && (
        <Section title="Interpretation">
          <p className="text-slate-700">{intent.reasoning}</p>
          <dl className="mt-2 grid grid-cols-2 gap-1 text-xs text-slate-600">
            <dt>Sectors</dt>
            <dd>{intent.sectors?.join(", ") || "all"}</dd>
            <dt>Metrics</dt>
            <dd>{intent.metrics?.join(", ")}</dd>
            <dt>Period</dt>
            <dd>
              {intent.start_year}–{intent.end_year}
            </dd>
            <dt>Analyses</dt>
            <dd>{intent.analysis_types?.join(", ")}</dd>
            <dt>Confidence</dt>
            <dd>{Math.round((intent.confidence ?? 0) * 100)}%</dd>
          </dl>
        </Section>
      )}
      {plan && (
        <Section title="Plan">
          <p className="mb-2 text-xs text-slate-500">{plan.reasoning}</p>
          <ol className="space-y-1.5">
            {plan.tasks.map((t: PlanTask) => (
              <li key={t.id} className="flex gap-2 rounded border border-slate-100 p-2 text-xs">
                <b className="w-7 shrink-0">{t.id}</b>
                <span className="w-20 shrink-0 font-medium capitalize text-slate-700">{t.agent}</span>
                <span className="w-16 shrink-0 text-slate-500">{t.source}</span>
                <span className="text-slate-700">{t.description}</span>
              </li>
            ))}
          </ol>
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {children}
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="py-10 text-center text-sm text-slate-400">{text}</p>;
}
