import { Progress as P } from "radix-ui";
import { cn } from "./cn";

/** Quality score 0-1 as a labelled bar (role="progressbar" with aria values from Radix). */
export function ScoreBar({ score }: { score: number }) {
  const color = score >= 0.85 ? "bg-ok" : score >= 0.6 ? "bg-warn" : "bg-danger";
  const pct = Math.round(score * 100);
  return (
    <div className="flex items-center gap-2">
      <P.Root
        value={pct}
        aria-label="Data quality score"
        className="relative h-1.5 w-20 overflow-hidden rounded-full bg-surface-sunken"
      >
        <P.Indicator className={cn("h-full", color)} style={{ width: `${pct}%` }} />
      </P.Root>
      <span className="text-xs tabular-nums text-muted">{score.toFixed(2)}</span>
    </div>
  );
}

/** Run progress. `value` null = indeterminate (queued / unknown). */
export function StageProgress({ value, label }: { value: number | null; label: string }) {
  return (
    <P.Root
      value={value}
      aria-label={label}
      className="relative h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken"
    >
      {value === null ? (
        <P.Indicator className="h-full w-2/5 animate-indeterminate rounded-full bg-brand-500" />
      ) : (
        <P.Indicator className="h-full rounded-full bg-brand-600 transition-[width]" style={{ width: `${value}%` }} />
      )}
    </P.Root>
  );
}
