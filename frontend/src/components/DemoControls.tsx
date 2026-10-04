import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Card } from "./ui";

/** Chaos toggles to demonstrate failure handling on cue (plan.md §4.4). */
export default function DemoControls() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["chaos"], queryFn: api.chaos });
  const update = useMutation({
    mutationFn: api.setChaos,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chaos"] });
      qc.invalidateQueries({ queryKey: ["config"] });
    },
  });
  const sources: string[] = data?.fail_sources ?? [];
  const llms: string[] = data?.fail_llm ?? [];
  const toggle = (list: string[], item: string) => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);

  return (
    <Card title="Demo controls (chaos)">
      <div className="space-y-2 text-sm">
        <Toggle
          label="SingStat MCP down"
          on={sources.includes("singstat_mcp")}
          onChange={() => update.mutate({ fail_sources: toggle(sources, "singstat_mcp") })}
        />
        <Toggle
          label="Data.gov.sg down"
          on={sources.includes("datagov")}
          onChange={() => update.mutate({ fail_sources: toggle(sources, "datagov") })}
        />
        <Toggle
          label="OpenAI down"
          on={llms.includes("openai")}
          onChange={() => update.mutate({ fail_llm: toggle(llms, "openai") })}
        />
        <Toggle
          label="Inject a hallucination (writer, 1st draft)"
          on={Boolean(data?.inject_hallucination)}
          onChange={() => update.mutate({ inject_hallucination: !data?.inject_hallucination })}
        />
      </div>
      <p className="mt-3 text-xs text-slate-500">Applies to the next run. Watch the timeline for fallbacks.</p>
    </Card>
  );
}

function Toggle({ label, on, onChange }: { label: string; on: boolean; onChange: () => void }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-2">
      <span className="text-slate-700">{label}</span>
      <button
        type="button"
        onClick={onChange}
        className={`relative h-5 w-9 rounded-full transition ${on ? "bg-red-500" : "bg-slate-300"}`}
        aria-pressed={on}
      >
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition ${on ? "left-4.5" : "left-0.5"}`} />
      </button>
    </label>
  );
}
