import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useToast } from "./ui";

/** Inline, non-modal: the timeline stays visible. Focus moves here when the run asks for input. */
export default function ClarificationCard({
  runId,
  question,
  suggestions,
  onAnswered,
}: {
  runId: string;
  question: string;
  suggestions: string[];
  onAnswered: () => void;
}) {
  const [answer, setAnswer] = useState("");
  const toast = useToast();
  const card = useRef<HTMLDivElement>(null);
  const send = useMutation({
    mutationFn: (a: string) => api.clarify(runId, a),
    onSuccess: onAnswered,
    onError: (e) => toast({ title: "Could not send your answer", description: (e as Error).message, tone: "error" }),
  });

  useEffect(() => {
    card.current?.focus();
  }, []);

  return (
    <div
      ref={card}
      tabIndex={-1}
      role="alert"
      aria-live="assertive"
      className="rounded-xl border border-amber-300 bg-amber-50 p-4"
    >
      <p className="text-sm font-semibold text-amber-900">The coordinator needs a clarification</p>
      <p className="mt-1 text-sm text-amber-900">{question}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {suggestions.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => send.mutate(s)}
            disabled={send.isPending}
            className="rounded-full border border-amber-300 bg-white px-3 py-1 text-xs text-amber-900 hover:bg-amber-100 disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (answer.trim()) send.mutate(answer.trim());
        }}
      >
        <input
          aria-label="Your answer"
          className="flex-1 rounded-md border border-amber-300 px-3 py-1.5 text-sm"
          placeholder="Or type your own answer"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
        />
        <button className="rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50" disabled={send.isPending}>
          Continue
        </button>
      </form>
    </div>
  );
}
