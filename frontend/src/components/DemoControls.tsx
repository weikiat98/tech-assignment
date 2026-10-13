import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Card, Switch, useToast } from "./ui";

/** Chaos toggles to demonstrate failure handling on cue (plan.md §4.4). */
export default function DemoControls() {
  const qc = useQueryClient();
  const toast = useToast();
  const { data } = useQuery({ queryKey: ["chaos"], queryFn: api.chaos });
  const update = useMutation({
    mutationFn: api.setChaos,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chaos"] });
      qc.invalidateQueries({ queryKey: ["config"] });
    },
    onError: (e) => toast({ title: "Could not update the demo toggle", description: (e as Error).message, tone: "error" }),
  });
  const sources: string[] = data?.fail_sources ?? [];
  const llms: string[] = data?.fail_llm ?? [];
  const toggle = (list: string[], item: string) => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);

  if (data?.enabled === false) {
    return (
      <Card title="Demo controls (chaos)">
        <p className="text-xs text-slate-500">
          Disabled on this deployment. Failure toggles are available when running locally.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Demo controls (chaos)">
      <div className="space-y-2">
        <Switch
          tone="danger"
          label="SingStat MCP down"
          checked={sources.includes("singstat_mcp")}
          onCheckedChange={() => update.mutate({ fail_sources: toggle(sources, "singstat_mcp") })}
        />
        <Switch
          tone="danger"
          label="SingStat REST API down"
          checked={sources.includes("singstat_rest")}
          onCheckedChange={() => update.mutate({ fail_sources: toggle(sources, "singstat_rest") })}
        />
        <Switch
          tone="danger"
          label="Data.gov.sg down"
          checked={sources.includes("datagov")}
          onCheckedChange={() => update.mutate({ fail_sources: toggle(sources, "datagov") })}
        />
        <Switch
          tone="danger"
          label="OpenAI down"
          checked={llms.includes("openai")}
          onCheckedChange={() => update.mutate({ fail_llm: toggle(llms, "openai") })}
        />
        <Switch
          tone="danger"
          label="Inject a hallucination (writer, 1st draft)"
          checked={Boolean(data?.inject_hallucination)}
          onCheckedChange={() => update.mutate({ inject_hallucination: !data?.inject_hallucination })}
        />
      </div>
      <p className="mt-3 text-xs text-slate-500">Applies to the next run. Watch the timeline for fallbacks.</p>
    </Card>
  );
}
