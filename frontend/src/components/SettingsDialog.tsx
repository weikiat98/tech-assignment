import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import DemoControls from "./DemoControls";
import { Card, Modal } from "./ui";

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted">{k}</dt>
      <dd className="text-right font-medium text-ink">{v}</dd>
    </div>
  );
}

/** System status and the demo failure toggles (todo.md CL-e): out of the way of the chat, one click from any page. */
export default function SettingsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { data: cfg } = useQuery({ queryKey: ["public-config"], queryFn: api.publicConfig, enabled: open });
  const { data: runtime } = useQuery({ queryKey: ["config"], queryFn: api.config, enabled: open });
  return (
    <Modal open={open} onOpenChange={onOpenChange} title="Settings">
      <div className="grid gap-4 md:grid-cols-2">
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
    </Modal>
  );
}
