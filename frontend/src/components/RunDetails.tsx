import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { RunSummary } from "../lib/types";
import { Modal, cn } from "./ui";

const STATE_LABEL: Record<RunSummary["sources"][number]["state"], { text: string; cls: string }> = {
  live: { text: "Live", cls: "bg-ok-bg text-ok" },
  saved_copy: { text: "Saved copy", cls: "bg-warn-bg text-warn" },
  failed: { text: "Failed", cls: "bg-danger-bg text-danger" },
};

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : `${Math.round(v * 100)}%`);

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1.5">
      <dt className="text-muted">{k}</dt>
      <dd className="text-right text-ink">{children}</dd>
    </div>
  );
}

/** Plain-language facts about one run (todo.md CL14): the short version of what Langfuse shows engineers. */
export default function RunDetails({ runId, open, onOpenChange }: { runId: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { data: s, error } = useQuery({ queryKey: ["summary", runId], queryFn: () => api.summary(runId), enabled: open });
  return (
    <Modal open={open} onOpenChange={onOpenChange} title="Run details">
      {error && <p role="alert" className="text-sm text-danger">Could not load the run details.</p>}
      {!s && !error && <p className="text-sm text-muted">Loading…</p>}
      {s && (
        <div className="space-y-4 text-sm">
          <dl className="divide-y divide-line rounded-lg border border-line px-3">
            <Row k="Outcome">
              {s.status}
              {s.verified !== null && (s.verified ? " · every claim verified" : " · some claims removed")}
            </Row>
            <Row k="Time taken">{s.seconds === null ? "n/a" : `${s.seconds} s`}</Row>
            <Row k="AI model">{s.models.length ? s.models.join(", ") : "none"}{s.llm_fallbacks.length > 0 && ` (fallback: ${s.llm_fallbacks.join(", ")})`}</Row>
            <Row k="Cost">US${s.cost_usd.toFixed(4)}</Row>
            <Row k="Steps">
              {s.steps} · {s.retries.rewrites} rewrite{s.retries.rewrites === 1 ? "" : "s"}, {s.retries.replans} re-plan{s.retries.replans === 1 ? "" : "s"},{" "}
              {s.retries.failed_steps} failed step{s.retries.failed_steps === 1 ? "" : "s"}
            </Row>
            <Row k="Checks">
              numbers {pct(s.checks.numeric_pass_rate)} · citations {pct(s.checks.citation_pass_rate)} · entities {pct(s.checks.entity_pass_rate)}
            </Row>
            {s.facts_from_earlier_questions > 0 && <Row k="Reused">{s.facts_from_earlier_questions} facts from earlier questions in this chat</Row>}
          </dl>

          <section aria-label="Data sources">
            <h3 className="mb-1.5 text-xs font-medium text-muted">Data sources</h3>
            <ul className="space-y-1.5">
              {s.sources.length === 0 && <li className="text-muted">No data was collected.</li>}
              {s.sources.map((x, i) => (
                <li key={`${x.key}-${i}`} className="flex items-start gap-2">
                  <span className={cn("mt-0.5 shrink-0 rounded-sm px-1.5 text-2xs font-semibold", STATE_LABEL[x.state].cls)}>{STATE_LABEL[x.state].text}</span>
                  <span className="min-w-0 break-words text-ink">
                    {x.title}
                    {x.agency && <span className="text-muted"> · {x.agency}</span>}
                    {x.quality !== null && <span className="text-muted"> · quality {x.quality.toFixed(2)}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          {s.worth_knowing.length > 0 && (
            <section aria-label="Worth knowing" className="rounded-lg border border-warn/40 bg-warn-bg p-3">
              <h3 className="mb-1 text-xs font-semibold text-warn">Worth knowing</h3>
              <ul className="list-disc space-y-1 pl-5 text-ink">
                {s.worth_knowing.map((w) => (
                  <li key={w} className="break-words">
                    {w}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {s.trace_url && (
            <p className="text-xs text-muted">
              For engineers:{" "}
              <a href={s.trace_url} target="_blank" rel="noreferrer" className="text-brand-700 underline">
                open the Langfuse trace
              </a>
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}
