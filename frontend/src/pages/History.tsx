import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Card, StatusBadge } from "../components/ui";

export default function History() {
  const [q, setQ] = useState("");
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({ queryKey: ["analyses", q], queryFn: () => api.listAnalyses(q || undefined) });
  const rerun = useMutation({ mutationFn: api.rerun, onSuccess: (a) => navigate(`/analyses/${a.id}`) });
  const remove = useMutation({ mutationFn: api.remove, onSuccess: () => qc.invalidateQueries({ queryKey: ["analyses"] }) });

  return (
    <Card
      title="Analysis history"
      actions={
        <input
          className="w-64 rounded-md border border-slate-300 px-2 py-1 text-sm"
          placeholder="Search questions…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      }
    >
      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {data && data.length === 0 && <p className="text-sm text-slate-500">No analyses yet.</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-slate-500">
              <th className="py-2 pr-3">Question</th>
              <th className="py-2 pr-3">Status</th>
              <th className="py-2 pr-3">Started</th>
              <th className="py-2 pr-3">Duration</th>
              <th className="py-2 pr-3">Cost</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {data?.map((a) => {
              const secs = a.finished_at ? (new Date(a.finished_at).getTime() - new Date(a.created_at).getTime()) / 1000 : null;
              return (
                <tr key={a.id} className="border-t border-slate-100">
                  <td className="max-w-xl py-2 pr-3">
                    <Link to={`/analyses/${a.id}`} className="text-brand-700 hover:underline">
                      {a.query}
                    </Link>
                  </td>
                  <td className="py-2 pr-3">
                    <StatusBadge status={a.status} />
                  </td>
                  <td className="whitespace-nowrap py-2 pr-3 text-xs text-slate-500">{new Date(a.created_at).toLocaleString()}</td>
                  <td className="py-2 pr-3 text-xs text-slate-500">{secs !== null ? `${secs.toFixed(0)}s` : "-"}</td>
                  <td className="py-2 pr-3 text-xs tabular-nums text-slate-500">${Number(a.total_cost_usd).toFixed(4)}</td>
                  <td className="whitespace-nowrap py-2 text-right text-xs">
                    <button className="mr-3 text-slate-600 hover:text-brand-700" onClick={() => rerun.mutate(a.id)}>
                      Re-run
                    </button>
                    <button className="text-slate-400 hover:text-red-600" onClick={() => remove.mutate(a.id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
