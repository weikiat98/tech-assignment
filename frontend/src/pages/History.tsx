import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { AnalysisSummary } from "../lib/types";
import {
  Button,
  Card,
  ConfirmDialog,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  StatusBadge,
  ToggleGroup,
  ToggleGroupItem,
  useToast,
} from "../components/ui";

const STATUS_FILTERS = [
  { value: "completed", label: "Completed" },
  { value: "running", label: "Running" },
  { value: "awaiting_input", label: "Needs input" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
] as const;

/** Pure filter, exported for tests. No statuses selected means "all". */
export function filterByStatus(rows: AnalysisSummary[], statuses: string[]): AnalysisSummary[] {
  if (statuses.length === 0) return rows;
  return rows.filter((a) => statuses.includes(a.status) || (statuses.includes("running") && a.status === "queued"));
}

export default function History() {
  const [q, setQ] = useState("");
  const [statuses, setStatuses] = useState<string[]>([]);
  const [pendingDelete, setPendingDelete] = useState<AnalysisSummary | null>(null);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const { data, isLoading } = useQuery({ queryKey: ["analyses", q], queryFn: () => api.listAnalyses(q || undefined) });
  const rows = useMemo(() => (data ? filterByStatus(data, statuses) : undefined), [data, statuses]);
  const rerun = useMutation({
    mutationFn: api.rerun,
    onSuccess: (a) => navigate(`/analyses/${a.id}`),
    onError: (e) => toast({ title: "Could not re-run the analysis", description: (e as Error).message, tone: "error" }),
  });
  const remove = useMutation({
    mutationFn: api.remove,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["analyses"] });
      toast({ title: "Analysis deleted", tone: "success" });
    },
    onError: (e) => toast({ title: "Could not delete the analysis", description: (e as Error).message, tone: "error" }),
  });

  return (
    <Card
      title="Analysis history"
      actions={
        <input
          aria-label="Search questions"
          className="w-64 max-w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
          placeholder="Search questions…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      }
    >
      <ToggleGroup
        type="multiple"
        value={statuses}
        onValueChange={setStatuses}
        aria-label="Filter by status (none selected shows all)"
        className="mb-3 flex flex-wrap gap-1.5"
      >
        {STATUS_FILTERS.map((s) => (
          <ToggleGroupItem key={s.value} value={s.value}>
            {s.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {rows && rows.length === 0 && (
        <p className="py-6 text-center text-sm text-slate-400">
          {data && data.length > 0 ? "No analyses match these filters." : "No analyses yet. Ask a question to get started."}
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-slate-500">
              <th className="py-2 pr-3">Question</th>
              <th className="py-2 pr-3">Status</th>
              <th className="py-2 pr-3">Started</th>
              <th className="py-2 pr-3">Duration</th>
              <th className="py-2 pr-3">Cost</th>
              <th className="py-2">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows?.map((a) => {
              const secs = a.finished_at ? (new Date(a.finished_at).getTime() - new Date(a.created_at).getTime()) / 1000 : null;
              return (
                <tr key={a.id} className="border-t border-slate-100">
                  <td className="max-w-xl py-2 pr-3">
                    <Link to={`/analyses/${a.id}`} className="break-words text-brand-700 hover:underline">
                      {a.query}
                    </Link>
                  </td>
                  <td className="py-2 pr-3">
                    <StatusBadge status={a.status} />
                  </td>
                  <td className="whitespace-nowrap py-2 pr-3 text-xs text-slate-500">{new Date(a.created_at).toLocaleString()}</td>
                  <td className="py-2 pr-3 text-xs text-slate-500">{secs !== null ? `${secs.toFixed(0)}s` : "-"}</td>
                  <td className="py-2 pr-3 text-xs tabular-nums text-slate-500">${Number(a.total_cost_usd).toFixed(4)}</td>
                  <td className="whitespace-nowrap py-2 text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button size="sm" variant="ghost" aria-label={`Actions for: ${a.query}`}>
                          <span aria-hidden>⋯</span>
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent>
                        <DropdownMenuItem onSelect={() => rerun.mutate(a.id)}>Re-run</DropdownMenuItem>
                        <DropdownMenuItem tone="danger" onSelect={() => setPendingDelete(a)}>
                          Delete…
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(o) => !o && setPendingDelete(null)}
        title="Delete this analysis?"
        description={
          <>
            “{pendingDelete?.query}” and its report, charts and events will be removed. This can't be undone.
          </>
        }
        onConfirm={() => {
          if (pendingDelete) remove.mutate(pendingDelete.id);
          setPendingDelete(null);
        }}
      />
    </Card>
  );
}
