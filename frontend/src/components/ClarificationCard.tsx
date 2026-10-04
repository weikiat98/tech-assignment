import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../lib/api";

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
  const send = useMutation({ mutationFn: (a: string) => api.clarify(runId, a), onSuccess: onAnswered });
  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-4">
      <p className="text-sm font-semibold text-amber-900">The coordinator needs a clarification</p>
      <p className="mt-1 text-sm text-amber-900">{question}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => send.mutate(s)}
            className="rounded-full border border-amber-300 bg-white px-3 py-1 text-xs text-amber-900 hover:bg-amber-100"
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
          className="flex-1 rounded-md border border-amber-300 px-3 py-1.5 text-sm"
          placeholder="Or type your own answer"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
        />
        <button className="rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white" disabled={send.isPending}>
          Continue
        </button>
      </form>
      {send.error && <p className="mt-2 text-xs text-red-700">{(send.error as Error).message}</p>}
    </div>
  );
}
