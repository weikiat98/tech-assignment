import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useRunEvents } from "../lib/useRunEvents";
import { ChartsPanel, DataPanel, PlanPanel, ReportPanel } from "./ResultPanels";
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  useToast,
} from "./ui";

export const PREVIEW_TABS = ["Report", "Charts", "Data & quality", "Plan"] as const;
export type PreviewTab = (typeof PREVIEW_TABS)[number];

const EXPORTS = [
  { format: "md", label: "Markdown (.md)" },
  { format: "pdf", label: "PDF (.pdf)" },
  { format: "docx", label: "Word (.docx)" },
] as const;

/** One answer's report, charts, data quality and plan, with Export (todo.md CL5). */
export default function PreviewPanel({
  runId,
  tab,
  onTab,
  onClose,
}: {
  runId: string;
  tab: PreviewTab;
  onTab: (t: PreviewTab) => void;
  onClose: () => void;
}) {
  const toast = useToast();
  const { data: analysis } = useQuery({ queryKey: ["analysis", runId], queryFn: () => api.getAnalysis(runId) });
  const active = !analysis || ["queued", "running", "awaiting_input"].includes(analysis.status);
  const { events } = useRunEvents(runId, active);
  const result = analysis?.result ?? null;
  return (
    <section aria-label="Preview" className="flex h-full min-h-0 flex-col bg-surface">
      <Tabs value={tab} onValueChange={(v) => onTab(v as PreviewTab)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-line pr-2">
          <TabsList aria-label="Preview sections" className="min-w-0 flex-1 overflow-x-auto border-b-0">
            {PREVIEW_TABS.map((t) => (
              <TabsTrigger key={t} value={t}>
                {t}
              </TabsTrigger>
            ))}
          </TabsList>
          {result && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm">
                  Export <span aria-hidden>▾</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                {EXPORTS.map((x) => (
                  <DropdownMenuItem key={x.format} asChild onSelect={() => toast({ title: `Export started: ${x.label}` })}>
                    <a href={api.exportUrl(runId, x.format)}>{x.label}</a>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <Button size="sm" variant="ghost" onClick={onClose} aria-label="Close preview">
            <span aria-hidden>×</span>
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <TabsContent value="Report">
            <ReportPanel result={result} events={events} />
          </TabsContent>
          <TabsContent value="Charts">
            <ChartsPanel result={result} events={events} />
          </TabsContent>
          <TabsContent value="Data & quality">
            <DataPanel result={result} events={events} />
          </TabsContent>
          <TabsContent value="Plan">
            <PlanPanel events={events} />
          </TabsContent>
        </div>
      </Tabs>
    </section>
  );
}
