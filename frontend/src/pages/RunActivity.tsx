import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { RunActivityBucket, RunActivityPeriod } from "../lib/types";
import RunDetails from "../components/RunDetails";
import { Button, StatusBadge, ToggleGroup, ToggleGroupItem, cn } from "../components/ui";

const PERIODS: { value: RunActivityPeriod; label: string }[] = [
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "year", label: "Year" },
];

const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
const usd = (v: number) => `US$${v.toFixed(v > 0 && v < 0.01 ? 4 : 2)}`;
const when = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

/**
 * Every run across all chats (decision 26): totals per week, month or year with a running count, and the runs
 * in one period. Each run opens the Run details dialog.
 */
export default function RunActivity() {
  const [period, setPeriod] = useState<RunActivityPeriod>("week");
  const [picked, setPicked] = useState<string | null>(null);
  const [details, setDetails] = useState<string | null>(null);
  const { data, error } = useQuery({
    queryKey: ["activity", period, TZ],
    queryFn: () => api.activity(period, TZ),
    refetchInterval: (q) => ((q.state.data?.totals.active ?? 0) > 0 ? 5000 : false),
  });
  const buckets = data?.buckets ?? [];
  const selected = buckets.find((b) => b.start === picked) ?? buckets[0];
  const busiest = Math.max(1, ...buckets.map((b) => b.runs));

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-6 px-4 py-6">
        <header className="space-y-1">
          <h1 className="text-lg font-semibold text-ink">Run activity</h1>
          <p className="text-sm text-muted">Every question asked in every chat, counted by when it started ({TZ} time).</p>
        </header>

        <ToggleGroup
          type="single"
          value={period}
          onValueChange={(v) => {
            if (!v) return;
            setPeriod(v as RunActivityPeriod);
            setPicked(null);
          }}
          aria-label="Group runs by"
          className="flex gap-1.5"
        >
          {PERIODS.map((p) => (
            <ToggleGroupItem key={p.value} value={p.value} className="px-3 py-1 text-xs">
              {p.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>

        {error && <p role="alert" className="text-sm text-danger">Could not load run activity: {(error as Error).message}</p>}
        {!data && !error && <p className="text-sm text-muted">Loading…</p>}

        {data && (
          <>
            <dl aria-label="All time" className="flex flex-wrap gap-x-8 gap-y-3 rounded-lg border border-line bg-surface px-4 py-3">
              <Total k="Runs, all time" v={String(data.totals.runs)} />
              <Total k="Completed" v={String(data.totals.completed)} />
              <Total k="Verified" v={String(data.totals.verified)} />
              <Total k="Failed" v={String(data.totals.failed)} />
              {data.totals.active > 0 && <Total k="Running now" v={String(data.totals.active)} />}
              <Total k="AI cost" v={usd(data.totals.cost_usd)} />
            </dl>

            <div className="overflow-x-auto rounded-lg border border-line">
              <table className="w-full min-w-[640px] text-sm">
                <caption className="sr-only">Runs per {period}, newest first. Select a row to list its runs.</caption>
                <thead className="bg-surface text-left text-xs text-muted">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">{PERIODS.find((p) => p.value === period)?.label}</th>
                    <th scope="col" className="w-[30%] px-3 py-2 font-medium">Runs</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Completed</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Verified</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Failed</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">AI cost</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Running total</th>
                  </tr>
                </thead>
                <tbody>
                  {buckets.map((b) => (
                    <PeriodRow key={b.start} b={b} busiest={busiest} selected={b.start === selected?.start} onSelect={() => setPicked(b.start)} />
                  ))}
                </tbody>
              </table>
            </div>

            {selected && <PeriodRuns bucket={selected} onDetails={setDetails} />}
          </>
        )}
      </div>
      {details && <RunDetails runId={details} open onOpenChange={(o) => !o && setDetails(null)} />}
    </div>
  );
}

function Total({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{k}</dt>
      <dd className="text-lg font-semibold tabular-nums text-ink">{v}</dd>
    </div>
  );
}

function PeriodRow({ b, busiest, selected, onSelect }: { b: RunActivityBucket; busiest: number; selected: boolean; onSelect: () => void }) {
  return (
    <tr className={cn("border-t border-line", selected ? "bg-brand-50" : "hover:bg-surface-sunken/60")}>
      <th scope="row" className="px-3 py-1.5 text-left font-normal">
        <button
          type="button"
          onClick={onSelect}
          aria-pressed={selected}
          className={cn("rounded-sm text-left", selected ? "font-medium text-brand-700" : "text-ink hover:underline")}
        >
          {b.label}
        </button>
      </th>
      <td className="px-3 py-1.5">
        <div className="flex items-center gap-2">
          <span className="h-2.5 flex-1" aria-hidden>
            {b.runs > 0 && <span className="block h-full rounded-r-sm bg-brand-600" style={{ width: `${(b.runs / busiest) * 100}%` }} />}
          </span>
          <span className="w-8 text-right tabular-nums text-ink">{b.runs}</span>
        </div>
      </td>
      <td className="px-3 py-1.5 text-right tabular-nums text-ink">{b.completed}</td>
      <td className="px-3 py-1.5 text-right tabular-nums text-ink">{b.verified}</td>
      <td className={cn("px-3 py-1.5 text-right tabular-nums", b.failed ? "text-danger" : "text-ink")}>{b.failed}</td>
      <td className="px-3 py-1.5 text-right tabular-nums text-muted">{usd(b.cost_usd)}</td>
      <td className="px-3 py-1.5 text-right tabular-nums text-muted">{b.cumulative_runs}</td>
    </tr>
  );
}

/** The runs behind one period (artboard 5's run list); Details opens the per-run dialog. */
function PeriodRuns({ bucket, onDetails }: { bucket: RunActivityBucket; onDetails: (id: string) => void }) {
  const { data, error } = useQuery({
    queryKey: ["activity-runs", bucket.from, bucket.to, bucket.runs, bucket.active],
    queryFn: () => api.activityRuns(bucket.from, bucket.to),
    enabled: bucket.runs > 0,
  });
  return (
    <section aria-labelledby="period-runs" className="space-y-2">
      <h2 id="period-runs" className="text-base font-semibold text-ink">
        Runs in {bucket.label.replace(/^Week of/, "the week of")}
      </h2>
      {bucket.runs === 0 && <p className="text-sm text-muted">No questions were asked in this period.</p>}
      {error && <p role="alert" className="text-sm text-danger">Could not load the runs.</p>}
      {data && (
        <ol className="divide-y divide-line rounded-lg border border-line">
          {data.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
              <StatusBadge status={r.status} />
              <span className="min-w-0 flex-1 basis-60">
                {r.chat_id ? (
                  <Link to={`/chats/${r.chat_id}`} className="block truncate text-sm text-ink hover:underline" title={r.query}>
                    {r.query}
                  </Link>
                ) : (
                  <span className="block truncate text-sm text-ink" title={r.query}>{r.query}</span>
                )}
                <span className="block text-xs text-muted">
                  {when(r.created_at)}
                  {r.seconds !== null && ` · ${r.seconds} s`}
                  {r.verified && " · verified"}
                  {` · ${usd(r.cost_usd)}`}
                </span>
              </span>
              <Button size="sm" variant="ghost" onClick={() => onDetails(r.id)}>
                Details
              </Button>
            </li>
          ))}
        </ol>
      )}
      {data && data.length < bucket.runs && <p className="text-xs text-muted">Showing the newest {data.length} of {bucket.runs} runs.</p>}
    </section>
  );
}
