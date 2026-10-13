import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Button, Card, InlineSwitch } from "../components/ui";
import DemoControls from "../components/DemoControls";

export default function NewAnalysis() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [webContext, setWebContext] = useState(false);
  const { data: cfg } = useQuery({ queryKey: ["public-config"], queryFn: api.publicConfig });
  const { data: runtime } = useQuery({ queryKey: ["config"], queryFn: api.config });
  const create = useMutation({
    mutationFn: () => api.createAnalysis(query.trim(), webContext),
    onSuccess: (a) => navigate(`/analyses/${a.id}`),
  });

  return (
    <div className="mx-auto grid max-w-5xl gap-5 lg:grid-cols-[1fr_300px]">
      <div className="space-y-5">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Ask a research question</h1>
          <p className="mt-1 text-sm text-slate-500">
            A coordinator plans the work, extraction agents pull official data (SingStat via its MCP server,
            Data.gov.sg, MOM, internal systems and the web), an analytics agent computes the numbers, and a
            verifier checks every claim before you see it.
          </p>
        </div>
        <Card>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (query.trim().length >= 3) create.mutate();
            }}
          >
            <textarea
              aria-label="Research question"
              className="h-28 w-full resize-none rounded-lg border border-slate-300 p-3 text-sm focus:border-brand-500"
              placeholder="e.g. Analyse employment trends in the technology sector from 2020-2024"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <InlineSwitch label="Include web context (news, ministry reports)" checked={webContext} onCheckedChange={setWebContext} />
              <Button type="submit" variant="primary" disabled={create.isPending || query.trim().length < 3}>
                {create.isPending ? "Starting…" : "Run analysis"}
              </Button>
            </div>
            {create.error && <p role="alert" className="mt-2 text-sm text-red-600">{(create.error as Error).message}</p>}
          </form>
        </Card>
        <Card title="Sample questions">
          <div className="flex flex-wrap gap-2">
            {cfg?.sample_queries.map((q) => (
              <button
                key={q}
                onClick={() => setQuery(q)}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-left text-xs text-slate-700 hover:border-brand-500 hover:bg-brand-50"
              >
                {q}
              </button>
            ))}
          </div>
        </Card>
      </div>
      <div className="space-y-5">
        <Card title="System">
          <dl className="space-y-1.5 text-xs">
            <Row k="LLM chain" v={(runtime?.llm_chain ?? []).join(" → ") || "…"} />
            <Row k="Web search" v={(runtime?.web_search_chain ?? []).join(" → ") || "…"} />
            <Row k="Tracing" v={runtime?.langfuse_enabled ? "Langfuse on" : "off (no keys)"} />
            <Row k="Offline mode" v={runtime?.offline_mode ? "yes (snapshots)" : "no"} />
            <Row k="Version" v={cfg?.version ?? ""} />
          </dl>
        </Card>
        <DemoControls />
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-right font-medium text-slate-800">{v}</dd>
    </div>
  );
}
