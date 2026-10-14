import type { AnalysisStatus } from "../../lib/types";
import { cn } from "./cn";

const STATUS_STYLES: Record<string, string> = {
  queued: "bg-idle-bg text-idle",
  running: "bg-run-bg text-run",
  awaiting_input: "bg-warn-bg text-warn",
  completed: "bg-ok-bg text-ok",
  partial: "bg-caution-bg text-caution",
  failed: "bg-danger-bg text-danger",
  cancelled: "bg-idle-bg text-idle",
};

const STATUS_LABELS: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  awaiting_input: "Awaiting input",
  completed: "Completed",
  partial: "Partial",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function StatusBadge({ status }: { status: AnalysisStatus | string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
        STATUS_STYLES[status] ?? "bg-idle-bg text-idle",
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full bg-current", status === "running" && "animate-pulse")} aria-hidden />
      {STATUS_LABELS[status] ?? status.replace("_", " ")}
    </span>
  );
}

const TIER_STYLES = ["", "bg-ok-bg text-ok", "bg-run-bg text-run", "bg-warn-bg text-warn"];
const TIER_LABELS = ["", "Tier 1 · official", "Tier 2 · statistical", "Tier 3 · context only"];

export function TierBadge({ tier }: { tier: number }) {
  return <span className={cn("rounded-sm px-1.5 py-0.5 text-2xs font-medium", TIER_STYLES[tier])}>{TIER_LABELS[tier]}</span>;
}
