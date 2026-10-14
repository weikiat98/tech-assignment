import { lazy, Suspense, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AgentEvent, AnalysisResult, Chart, Claim, DatasetSummary, Fact } from "../lib/types";
import { markCitedNumbers } from "../lib/evidence";

/** Full dataset summary once the run has finished; only key/title/quality while it is still running. */
type DatasetView = Pick<DatasetSummary, "key" | "title" | "quality"> & Partial<DatasetSummary>;
type PlanTask = NonNullable<AnalysisResult["plan"]>["tasks"][number];

// Plotly is ~1 MB: load it only when a chart is first shown, not with the app shell.
const PlotlyChart = lazy(() => import("./PlotlyChart"));
import { Button, Collapsible, CollapsibleContent, CollapsibleTrigger, Modal, ScoreBar, TierBadge, Tooltip } from "./ui";

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
      <p className="font-sans text-xs text-warn">Draft {lastAttempt}, awaiting verification…</p>
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
    <Tooltip
      trigger={
        <button
          type="button"
          aria-label={`Fact ${fact.id}: ${fact.label}`}
          className="ml-1 inline-block cursor-help rounded-sm bg-evidence px-1.5 align-[1px] text-2xs font-semibold text-evidence-ink"
        >
          {fact.id}
        </button>
      }
    >
      <b className="font-semibold">{fact.label}</b>
      <br />
      {fact.display} · method: {fact.method}
      <br />
      source: {fact.source_keys.join(", ")}
      {fact.derived && (
        <>
          <br />
          <i>derived by this platform</i>
        </>
      )}
    </Tooltip>
  );
}

function ClaimList({ claims, facts }: { claims: Claim[]; facts: Map<string, Fact> }) {
  return (
    <ul className="list-disc space-y-2 pl-5 marker:text-line-strong">
      {claims.map((c, i) => (
        <li key={i} className="text-base">
          {markCitedNumbers(
            c.text,
            c.fact_ids.map((id) => facts.get(id)),
          ).map((seg, j) =>
            seg.cited ? (
              <span key={j} className="evidence-mark">
                {seg.text}
              </span>
            ) : (
              seg.text
            ),
          )}
          {c.fact_ids.map((id) => (
            <FactChip key={id} id={id} fact={facts.get(id)} />
          ))}
        </li>
      ))}
    </ul>
  );
}

/** The stamp, with the check rates in a tooltip so the answer itself stays quiet. */
export function VerifiedStamp({ verification: v }: { verification: AnalysisResult["verification"] }) {
  if (!v) return null;
  return (
    <Tooltip
      trigger={
        <button
          type="button"
          className={`rounded-sm px-2 py-0.5 text-xs font-semibold ${v.passed ? "bg-evidence text-evidence-ink" : "bg-warn-bg text-warn"}`}
        >
          {v.passed ? "Verified" : "Verified with removals"}
        </button>
      }
    >
      Numeric checks {(v.numeric_pass_rate * 100).toFixed(0)}%
      <br />
      Citations {(v.citation_pass_rate * 100).toFixed(0)}%
      <br />
      Entities {(v.entity_pass_rate * 100).toFixed(0)}%
      <br />
      Drafts: {v.attempt}
    </Tooltip>
  );
}

/** The answer in the chat: summary, findings and the rest of the verified report, without the checks bar. */
export function AnswerBody({ result }: { result: AnalysisResult }) {
  if (!result.report) return null;
  const facts = new Map(result.facts.map((f) => [f.id, f]));
  return (
    <div className="space-y-5">
      <Section title="Executive summary">
        <p className="max-w-[68ch] font-serif text-md">{result.report.executive_summary}</p>
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
              <li key={n.url} className="rounded-md border border-line p-3 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <a href={n.url} target="_blank" rel="noreferrer" className="font-medium text-brand-700 underline">
                    {n.title}
                  </a>
                  <TierBadge tier={n.trust_tier} />
                  {n.injection_flagged && <span className="rounded-sm bg-danger-bg px-1.5 py-0.5 text-2xs font-medium text-danger">Injection text removed</span>}
                </div>
                <p className="mt-1 break-words text-muted">“{n.excerpt.slice(0, 280)}…”</p>
              </li>
            ))}
          </ul>
        </Section>
      )}
      {result.report.limitations.length > 0 && (
        <Section title="Limitations">
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
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
  const [expanded, setExpanded] = useState<Chart | null>(null);
  const charts = result?.charts ?? events.filter((e) => e.type === "chart").map((e) => e.content as Chart);
  if (!charts.length) return <Empty text="Charts appear as the analytics agent creates them." />;
  return (
    <>
      <div className="grid gap-4 xl:grid-cols-2">
        {charts.map((c) => (
          <div key={c.id} className="min-w-0 rounded-md border border-line p-2">
            <Suspense fallback={<div className="h-[340px] animate-pulse rounded-md bg-surface-sunken" />}>
              <PlotlyChart chart={c} />
            </Suspense>
            <div className="flex items-center justify-between gap-2 px-2 pb-1">
              <p className="min-w-0 break-words text-2xs text-muted">Source: {c.source_keys.join(", ")}</p>
              <Button size="sm" variant="ghost" onClick={() => setExpanded(c)} aria-label={`Expand chart: ${c.title}`}>
                Expand
              </Button>
            </div>
          </div>
        ))}
      </div>
      <Modal open={expanded !== null} onOpenChange={(o) => !o && setExpanded(null)} title={expanded?.title ?? "Chart"}>
        {expanded && (
          <Suspense fallback={<div className="h-[520px] animate-pulse rounded-md bg-surface-sunken" />}>
            <PlotlyChart chart={expanded} height={520} />
          </Suspense>
        )}
      </Modal>
    </>
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
        <div key={d.key} className="rounded-md border border-line p-3">
          <div className="flex flex-wrap items-center gap-2">
            <code className="rounded-sm bg-surface-sunken px-1.5 font-mono text-xs text-muted">{d.key}</code>
            <span className="text-sm font-medium">{d.title}</span>
            {d.trust_tier && <TierBadge tier={d.trust_tier} />}
            {d.is_fallback && <span className="rounded-sm bg-warn-bg px-1.5 py-0.5 text-2xs font-medium text-warn">Fallback</span>}
            <span className="ml-auto">{d.quality && <ScoreBar score={d.quality.score} />}</span>
          </div>
          {d.agency && (
            <p className="mt-1 text-xs text-muted">
              {d.agency} · {d.frequency} · {d.period_range?.join("–")} · {d.row_count} rows ·{" "}
              {d.url && (
                <a className="text-brand-700 underline" href={d.url} target="_blank" rel="noreferrer">
                  source
                </a>
              )}
            </p>
          )}
          {d.fallback_reason && <p className="mt-1 text-xs text-warn">{d.fallback_reason}</p>}
          {d.quality && (
            <Collapsible defaultOpen={d.quality.issues.length > 0} className="mt-2">
              <CollapsibleTrigger className="text-xs font-medium text-brand-700 hover:underline">
                Checks &amp; cleaning actions ({d.quality.issues.length} issue{d.quality.issues.length === 1 ? "" : "s"},{" "}
                {d.quality.actions.length} action{d.quality.actions.length === 1 ? "" : "s"})
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="mt-2 grid gap-2 text-xs md:grid-cols-2">
                  <div>
                    <p className="font-medium text-ink">Checks</p>
                    <ul className="mt-1 space-y-0.5">
                      {d.quality.issues.length === 0 && <li className="text-ok">No issues found</li>}
                      {d.quality.issues.map((i, idx) => (
                        <li key={idx} className={i.severity === "error" ? "text-danger" : i.severity === "warning" ? "text-warn" : "text-muted"}>
                          [{i.check}] {i.message.slice(0, 220)}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="font-medium text-ink">Cleaning actions</p>
                    <ul className="mt-1 space-y-0.5 text-muted">
                      {d.quality.actions.length === 0 && <li>None needed</li>}
                      {d.quality.actions.map((a: string, idx: number) => (
                        <li key={idx}>{a}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </CollapsibleContent>
            </Collapsible>
          )}
        </div>
      ))}
      {cross.length > 0 && (
        <div className="rounded-md border border-line p-3 text-xs">
          <p className="font-medium text-ink">Cross-source consistency</p>
          <ul className="mt-1 space-y-0.5">
            {cross.map((e) => (
              <li key={e.seq} className={String(e.content.message).includes("DIVERGE") ? "text-warn" : "text-muted"}>
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
          <p className="text-ink">{intent.reasoning}</p>
          <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-xs text-muted">
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
          <p className="mb-2 text-xs text-muted">{plan.reasoning}</p>
          <ol className="space-y-1.5">
            {plan.tasks.map((t: PlanTask) => (
              <li key={t.id} className="flex flex-wrap gap-x-2 gap-y-0.5 rounded-md border border-line p-2 text-xs sm:flex-nowrap">
                <b className="w-7 shrink-0 font-semibold">{t.id}</b>
                <span className="w-20 shrink-0 font-medium capitalize text-ink">{t.agent}</span>
                <span className="w-16 shrink-0 text-muted">{t.source}</span>
                <span className="min-w-0 break-words text-ink">{t.description}</span>
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
      <h3 className="mb-2 text-sm font-semibold text-muted">{title}</h3>
      {children}
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="py-10 text-center text-sm text-muted">{text}</p>;
}
