import { useEffect, useId, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Button, useToast } from "./ui";

/**
 * Inline, non-modal: the timeline stays visible. When the run asks for input, focus moves to this region;
 * its heading names it and the question describes it, so a screen reader reads both but not the controls.
 */
export default function ClarificationCard({
  runId,
  question,
  suggestions,
  showInput = true,
  onAnswered,
}: {
  runId: string;
  question: string;
  suggestions: string[];
  /** False in the chat, where the chat bar takes the typed answer. */
  showInput?: boolean;
  onAnswered: () => void;
}) {
  const [answer, setAnswer] = useState("");
  const toast = useToast();
  const card = useRef<HTMLElement>(null);
  const headingId = useId();
  const questionId = useId();
  const send = useMutation({
    mutationFn: (a: string) => api.clarify(runId, a),
    onSuccess: onAnswered,
    onError: (e) => toast({ title: "Could not send your answer", description: (e as Error).message, tone: "error" }),
  });

  useEffect(() => {
    card.current?.focus();
  }, []);

  return (
    <section
      ref={card}
      tabIndex={-1}
      aria-labelledby={headingId}
      aria-describedby={questionId}
      className="rounded-lg border border-warn/40 bg-warn-bg p-4"
    >
      <h2 id={headingId} className="text-sm font-semibold text-warn">
        The coordinator needs a clarification
      </h2>
      <p id={questionId} className="mt-1 text-base text-ink">
        {question}
      </p>
      {suggestions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => send.mutate(s)}
              disabled={send.isPending}
              className="rounded-full border border-warn/40 bg-surface px-3 py-1 text-xs text-ink hover:border-warn disabled:opacity-50"
            >
              {s}
            </button>
          ))}
        </div>
      )}
      {!showInput && <p className="mt-3 text-xs text-muted">Pick a suggestion, or type your answer in the chat bar below.</p>}
      {showInput && (
      <form
        className="mt-3 flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (answer.trim()) send.mutate(answer.trim());
        }}
      >
        <input
          aria-label="Your answer"
          className="min-w-0 flex-1 rounded-md border border-line-strong bg-canvas px-3 py-1.5 text-sm text-ink"
          placeholder="Or type your own answer"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
        />
        <Button type="submit" variant="primary" disabled={send.isPending}>
          Send answer
        </Button>
      </form>
      )}
    </section>
  );
}
