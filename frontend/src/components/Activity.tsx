import { useMemo, useState } from "react";
import { activityLines, headline, stageSummaries, type ActivityLine } from "../lib/activity";
import { currentStage, stageProgress } from "../lib/stages";
import type { AgentEvent } from "../lib/types";
import {
  Button,
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
  Modal,
  ScrollArea,
  StageProgress,
  ToggleGroup,
  ToggleGroupItem,
  cn,
} from "./ui";

const TONE: Record<ActivityLine["tone"], string> = {
  normal: "text-ink",
  note: "text-warn",
  error: "text-danger",
};

function StageList({ events, finished }: { events: AgentEvent[]; finished: boolean }) {
  const stages = stageSummaries(events, finished);
  return (
    <ol className="space-y-1.5">
      {stages.map((s) => (
        <li key={s.stage} className="flex gap-2.5 text-sm">
          <span
            aria-hidden
            className={cn(
              "mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full text-2xs font-semibold",
              s.done ? "bg-ok-bg text-ok" : s.text ? "bg-run-bg text-run" : "bg-idle-bg text-idle",
            )}
          >
            {s.done ? "✓" : s.stage + 1}
          </span>
          <span className="min-w-0">
            <span className="font-medium text-ink">{s.label}</span>
            {s.text ? (
              <span className={cn("block break-words", s.tone === "note" ? "text-warn" : "text-muted")}>{s.text}</span>
            ) : (
              <span className="block text-muted">Not started</span>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}

/**
 * The agent's work as part of the answer (todo.md CL4): one line while it runs, one summary when done. Show
 * steps lists the seven stages; the full activity opens in a dialog.
 */
export default function ActivitySummary({ events, finished, connected }: { events: AgentEvent[]; finished: boolean; connected: boolean }) {
  const [full, setFull] = useState(false);
  const [open, setOpen] = useState(false);
  const h = useMemo(() => headline(events, finished), [events, finished]);
  const progress = stageProgress(events, finished);
  const running = !finished;
  return (
    <div className="rounded-lg border border-line bg-surface-sunken/50 px-3 py-2">
      <Collapsible open={open} onOpenChange={setOpen}>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className="min-w-0 flex-1 text-sm text-muted" aria-live="polite">
            {running && <span className={cn("mr-2 inline-block h-2 w-2 rounded-full align-middle", connected ? "animate-pulse bg-run" : "bg-line-strong")} aria-hidden />}
            {h.text}
            {h.notes > 0 && finished && <span className="sr-only"> (some steps used saved copies or fallbacks)</span>}
          </p>
          <CollapsibleTrigger className="rounded-md px-1.5 py-0.5 text-xs font-medium text-brand-700 hover:underline">
            {open ? "Hide steps" : "Show steps"}
          </CollapsibleTrigger>
          <Button size="sm" variant="ghost" onClick={() => setFull(true)}>
            Open the full activity
          </Button>
        </div>
        {running && (
          <div className="mt-2">
            <StageProgress value={progress} label="Analysis progress" />
          </div>
        )}
        <CollapsibleContent>
          <div className="pt-3">
            <StageList events={events} finished={finished} />
          </div>
        </CollapsibleContent>
      </Collapsible>
      <ActivityDialog open={full} onOpenChange={setFull} events={events} finished={finished} />
    </div>
  );
}

type Mode = "main" | "every";

/** Artboard 4: "Main steps" or "Every action", with the raw JSON under Technical details. */
export function ActivityDialog({
  open,
  onOpenChange,
  events,
  finished,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  events: AgentEvent[];
  finished: boolean;
}) {
  const [mode, setMode] = useState<Mode>("main");
  const lines = useMemo(() => activityLines(events), [events]);
  const reached = currentStage(events);
  return (
    <Modal open={open} onOpenChange={onOpenChange} title="Agent activity">
      <ToggleGroup type="single" value={mode} onValueChange={(v) => v && setMode(v as Mode)} aria-label="Level of detail" className="mb-3 flex gap-1.5">
        <ToggleGroupItem value="main" className="px-3 py-1 text-xs">
          Main steps
        </ToggleGroupItem>
        <ToggleGroupItem value="every" className="px-3 py-1 text-xs">
          Every action ({lines.length})
        </ToggleGroupItem>
      </ToggleGroup>
      <ScrollArea className="h-[60vh]" viewportClassName="pr-3">
        {mode === "main" ? (
          <StageList events={events} finished={finished} />
        ) : lines.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted">Waiting for the first step…</p>
        ) : (
          <ol className="space-y-1">
            {lines.map((l) => (
              <li key={l.seq}>
                <Collapsible className="rounded-md border border-line bg-surface">
                  <div className="flex items-start gap-2 px-2.5 py-1.5 text-sm">
                    <span className={cn("min-w-0 flex-1 break-words", TONE[l.tone])}>
                      {l.tone === "note" && <span className="mr-1.5 rounded-sm bg-warn-bg px-1 text-2xs font-semibold text-warn">Note</span>}
                      {l.text}
                    </span>
                    <CollapsibleTrigger className="shrink-0 rounded-md px-1.5 text-2xs text-muted hover:text-ink">
                      Technical details
                    </CollapsibleTrigger>
                  </div>
                  <CollapsibleContent>
                    <pre className="mx-2.5 mb-2 max-h-64 overflow-auto rounded-sm border border-line bg-canvas p-2 font-mono text-2xs text-ink">
                      {JSON.stringify({ agent: l.event.agent, type: l.event.type, ...l.event.content }, null, 2)}
                    </pre>
                  </CollapsibleContent>
                </Collapsible>
              </li>
            ))}
          </ol>
        )}
      </ScrollArea>
      {!finished && reached >= 0 && <p className="mt-2 text-xs text-muted">Still running. New steps appear here as they happen.</p>}
    </Modal>
  );
}
