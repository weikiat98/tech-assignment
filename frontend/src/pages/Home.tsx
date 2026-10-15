import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useMessageOptions } from "../lib/useMessageOptions";
import ChatBar, { OptionChips } from "../components/ChatBar";
import { useToast } from "../components/ui";

/** Search-first start page (todo.md CL2): wordmark, tagline, one chat bar, sample questions. */
export default function Home() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [options, setOptions] = useMessageOptions();
  const { data: cfg } = useQuery({ queryKey: ["public-config"], queryFn: api.publicConfig });
  const create = useMutation({
    mutationFn: () => api.createChat(query.trim(), options),
    onSuccess: (chat) => {
      qc.invalidateQueries({ queryKey: ["chats"] });
      navigate(`/chats/${chat.id}`);
    },
    onError: (e) => toast({ title: "Could not start the analysis", description: (e as Error).message, tone: "error" }),
  });

  return (
    <div className="mx-auto flex h-full w-full max-w-3xl flex-col justify-center gap-6 overflow-y-auto px-4 py-10">
      <div className="text-center">
        <h1 className="text-[44px] font-semibold leading-[52px] text-ink">OWL</h1>
        <p className="mt-2 text-md text-muted text-balance">
          Ask about Singapore's economy and labour market. Every number in the answer is checked against official data.
        </p>
      </div>
      <ChatBar
        value={query}
        onChange={setQuery}
        onSend={() => create.mutate()}
        sending={create.isPending}
        placeholder="e.g. Analyse employment trends in the technology sector from 2020-2024"
        options={options}
        onOptions={setOptions}
        autoFocus
        footer={<OptionChips options={options} />}
      />
      <section aria-label="Sample questions">
        <h2 className="mb-2 text-xs font-medium text-muted">Try one of these</h2>
        <ul className="flex flex-wrap gap-2">
          {cfg?.sample_queries.map((q) => (
            <li key={q}>
              <button
                type="button"
                onClick={() => setQuery(q)}
                className="rounded-full border border-line bg-surface-sunken px-3 py-1 text-left text-xs text-ink hover:border-brand-500 hover:bg-brand-50"
              >
                {q}
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
