import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { answerText } from "../lib/chats";
import { useRunEvents } from "../lib/useRunEvents";
import { useRunToasts } from "../lib/useRunToasts";
import type { ChatTurn } from "../lib/types";
import ActivitySummary from "./Activity";
import ClarificationCard from "./ClarificationCard";
import RunDetails from "./RunDetails";
import { PREVIEW_TABS, type PreviewTab } from "./PreviewPanel";
import { AnswerBody, VerifiedStamp } from "./ResultPanels";
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  useToast,
} from "./ui";

export const ACTIVE = new Set(["queued", "running", "awaiting_input"]);

/** Copies text and reports "Copied" for a moment. */
function useCopy() {
  const [copied, setCopied] = useState(false);
  const toast = useToast();
  const timer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => () => clearTimeout(timer.current), []);
  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 1800);
    } catch {
      toast({ title: "Could not copy", description: "Your browser blocked access to the clipboard.", tone: "error" });
    }
  };
  return [copied, copy] as const;
}

/**
 * One question and its answer (todo.md CL3). A retry adds a version; the newest is shown and the earlier
 * ones stay reachable with the "Answer 1 of 2" switch.
 */
export default function Turn({
  chatId,
  item,
  isLast,
  previewRunId,
  onPreview,
  onFollowUp,
  onAnswered,
}: {
  chatId: string;
  item: ChatTurn;
  isLast: boolean;
  previewRunId: string | null;
  onPreview: (runId: string, tab: PreviewTab) => void;
  onFollowUp: (text: string) => void;
  onAnswered: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [picked, setPicked] = useState<number | null>(null);
  const count = item.versions.length;
  useEffect(() => setPicked(null), [count]); // a new retry always shows its own answer
  const index = picked ?? count - 1;
  const version = item.versions[index];
  const runId = version.id;
  const [questionCopied, copyQuestion] = useCopy();
  const [answerCopied, copyAnswer] = useCopy();
  const [details, setDetails] = useState(false);

  const { data: analysis } = useQuery({
    queryKey: ["analysis", runId],
    queryFn: () => api.getAnalysis(runId),
    refetchInterval: (q) => (q.state.data && ACTIVE.has(q.state.data.status) ? 4000 : false),
  });
  const status = analysis?.status ?? version.status;
  const active = ACTIVE.has(status);
  const { events, connected, liveAfter } = useRunEvents(runId, active);
  useRunToasts(events, liveAfter);

  // Refresh stored results as soon as the run reports completion, a question or an error.
  const last = events[events.length - 1];
  useEffect(() => {
    if (last && ["final", "clarification", "error"].includes(last.type)) {
      qc.invalidateQueries({ queryKey: ["analysis", runId] });
      qc.invalidateQueries({ queryKey: ["chat", chatId] });
      qc.invalidateQueries({ queryKey: ["chats"] });
    }
  }, [last, runId, chatId, qc]);

  const retry = useMutation({
    mutationFn: () => api.retryTurn(chatId, item.turn),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chat", chatId] });
      qc.invalidateQueries({ queryKey: ["chats"] });
    },
    onError: (e) => toast({ title: "Could not ask again", description: (e as Error).message, tone: "error" }),
  });
  const stop = useMutation({
    mutationFn: () => api.cancel(runId),
    onSuccess: () => toast({ title: "Stopping the run…" }),
    onError: (e) => toast({ title: "Could not stop the run", description: (e as Error).message, tone: "error" }),
  });

  const result = analysis?.result ?? null;
  const clarification = [...events].reverse().find((e) => e.type === "clarification")?.content;
  const outOfScope = result?.outcome === "out_of_scope" || (status === "completed" && result && !result.report);

  return (
    <article aria-label={`Question ${item.turn}`} className="space-y-3">
      <div className="flex flex-col items-end gap-1">
        <p className="max-w-[88%] whitespace-pre-wrap break-words rounded-xl bg-brand-100 px-3.5 py-2 text-base text-ink">{item.query}</p>
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" onClick={() => copyQuestion(item.query)}>
            {questionCopied ? "Copied" : "Copy"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => retry.mutate()} disabled={retry.isPending || active}>
            Ask this question again
          </Button>
        </div>
      </div>

      <div className="space-y-3">
        <ActivitySummary events={events} finished={!active} connected={connected} />

        {status === "awaiting_input" && clarification && (
          <ClarificationCard
            runId={runId}
            question={clarification.question}
            suggestions={clarification.suggestions ?? []}
            showInput={false}
            onAnswered={() => {
              qc.invalidateQueries({ queryKey: ["analysis", runId] });
              onAnswered();
            }}
          />
        )}
        {status === "failed" && (
          <div role="alert" className="rounded-md border border-danger/40 bg-danger-bg p-3 text-sm text-danger">
            The run failed: {analysis?.error ?? "unknown error"}
          </div>
        )}
        {status === "cancelled" && <p className="text-sm text-muted">Stopped before the answer was finished.</p>}
        {outOfScope && (
          <p className="rounded-md border border-line bg-surface-sunken/50 p-3 text-sm text-muted">
            This question is outside what OWL can analyse: {result?.intent?.reasoning || "it is not about Singapore policy, economy or labour data."}
          </p>
        )}
        {result?.report && <AnswerBody result={result} />}

        {(result?.report || active) && (
          <div className="flex flex-wrap items-center gap-1.5 border-t border-line pt-2">
            {result?.report && (
              <>
                <VerifiedStamp verification={result.verification} />
                <div className="inline-flex">
                  <Button
                    size="sm"
                    className="rounded-r-none"
                    aria-pressed={previewRunId === runId}
                    onClick={() => onPreview(runId, "Report")}
                  >
                    Preview
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button size="sm" className="rounded-l-none border-l-0" aria-label="Choose what to preview">
                        <span aria-hidden>▾</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start">
                      {PREVIEW_TABS.map((t) => (
                        <DropdownMenuItem key={t} onSelect={() => onPreview(runId, t)}>
                          {t}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => copyAnswer(answerText(result.report!.executive_summary, result.report!.key_findings.map((c) => c.text)))}
                >
                  {answerCopied ? "Copied" : "Copy"}
                </Button>
              </>
            )}
            {!active && (
              <Button size="sm" variant="ghost" onClick={() => setDetails(true)}>
                Run details
              </Button>
            )}
            {active ? (
              <Button size="sm" variant="ghost" onClick={() => stop.mutate()} disabled={stop.isPending}>
                Stop
              </Button>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => retry.mutate()} disabled={retry.isPending}>
                Retry
              </Button>
            )}
            {count > 1 && (
              <span className="ml-auto inline-flex items-center gap-1 text-xs text-muted">
                <Button size="sm" variant="ghost" aria-label="Previous answer" disabled={index === 0} onClick={() => setPicked(index - 1)}>
                  <span aria-hidden>‹</span>
                </Button>
                <span aria-live="polite">
                  Answer {index + 1} of {count}
                </span>
                <Button size="sm" variant="ghost" aria-label="Next answer" disabled={index === count - 1} onClick={() => setPicked(index + 1)}>
                  <span aria-hidden>›</span>
                </Button>
              </span>
            )}
          </div>
        )}

        {isLast && !active && result?.suggestions && result.suggestions.length > 0 && (
          <ul aria-label="Follow-up questions" className="flex flex-wrap gap-2">
            {result.suggestions.map((s) => (
              <li key={s}>
                <button
                  type="button"
                  onClick={() => onFollowUp(s)}
                  className="rounded-full border border-line bg-surface-sunken px-3 py-1 text-left text-xs text-ink hover:border-brand-500 hover:bg-brand-50"
                >
                  {s}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <RunDetails runId={runId} open={details} onOpenChange={setDetails} />
    </article>
  );
}
