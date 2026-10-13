import type { AnalysisStatus } from "../../lib/types";

const STATUS_STYLES: Record<string, string> = {
  queued: "bg-slate-100 text-slate-700",
  running: "bg-blue-100 text-blue-700",
  awaiting_input: "bg-amber-100 text-amber-800",
  completed: "bg-emerald-100 text-emerald-700",
  partial: "bg-orange-100 text-orange-700",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-slate-200 text-slate-600",
};

export function StatusBadge({ status }: { status: AnalysisStatus | string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status] ?? ""}`}>
      {status === "running" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-600" />}
      {status.replace("_", " ")}
    </span>
  );
}

export function TierBadge({ tier }: { tier: number }) {
  const styles = ["", "bg-emerald-50 text-emerald-700 ring-emerald-200", "bg-sky-50 text-sky-700 ring-sky-200",
    "bg-amber-50 text-amber-800 ring-amber-200"];
  const labels = ["", "Tier 1 · official", "Tier 2 · statistical", "Tier 3 · context only"];
  return <span className={`rounded px-1.5 py-0.5 text-[11px] ring-1 ${styles[tier]}`}>{labels[tier]}</span>;
}
