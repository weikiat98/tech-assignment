import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useMessageOptions } from "../lib/useMessageOptions";
import ChatBar, { OptionChips } from "../components/ChatBar";
import PreviewPanel, { type PreviewTab } from "../components/PreviewPanel";
import { useShell } from "../components/shell";
import Turn, { ACTIVE } from "../components/Turn";
import { Button, ScrollArea, Sheet, StatusBadge, useToast } from "../components/ui";

/** A conversation (todo.md CL3): the thread, the chat bar and, on request, the preview panel. */
export default function Chat() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const toast = useToast();
  const { isDesktop, setPreviewOpen } = useShell();
  const [text, setText] = useState("");
  const [options, setOptions] = useMessageOptions();
  const [preview, setPreview] = useState<{ runId: string; tab: PreviewTab } | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const { data: chat, error } = useQuery({
    queryKey: ["chat", id],
    queryFn: () => api.getChat(id!),
    enabled: Boolean(id),
    retry: false,
    refetchInterval: (q) => {
      const items = q.state.data?.items ?? [];
      const last = items[items.length - 1]?.versions.at(-1);
      return last && ACTIVE.has(last.status) ? 4000 : false;
    },
  });
  const lastTurn = chat?.items[chat.items.length - 1];
  const lastRun = lastTurn?.versions[lastTurn.versions.length - 1];
  const awaiting = lastRun?.status === "awaiting_input";
  const busy = Boolean(lastRun && ACTIVE.has(lastRun.status) && !awaiting);

  // The preview belongs to one chat: close it when the chat changes or the page goes away.
  useEffect(() => {
    setPreview(null);
    setPreviewOpen(false);
    return () => setPreviewOpen(false);
  }, [id, setPreviewOpen]);
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [chat?.items.length, lastRun?.id, lastRun?.status]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["chat", id] });
    qc.invalidateQueries({ queryKey: ["chats"] });
  };
  const send = useMutation({
    mutationFn: (query: string) => api.sendMessage(id!, query, options),
    onSuccess: () => {
      setText("");
      refresh();
    },
    onError: (e) => toast({ title: "Could not send the question", description: (e as Error).message, tone: "error" }),
  });
  const clarify = useMutation({
    mutationFn: (answer: string) => api.clarify(lastRun!.id, answer),
    onSuccess: () => {
      setText("");
      qc.invalidateQueries({ queryKey: ["analysis", lastRun?.id] });
      refresh();
    },
    onError: (e) => toast({ title: "Could not send your answer", description: (e as Error).message, tone: "error" }),
  });
  const stop = useMutation({
    mutationFn: () => api.cancel(lastRun!.id),
    onSuccess: () => toast({ title: "Stopping the run…" }),
    onError: (e) => toast({ title: "Could not stop the run", description: (e as Error).message, tone: "error" }),
  });

  const openPreview = (runId: string, tab: PreviewTab) => {
    setPreview({ runId, tab });
    setPreviewOpen(true);
  };
  const closePreview = () => {
    setPreview(null);
    setPreviewOpen(false);
  };
  const submit = (query: string) => (awaiting ? clarify.mutate(query) : send.mutate(query));

  if (error) {
    return (
      <div className="mx-auto max-w-md p-10 text-center">
        <p role="alert" className="text-base text-ink">This chat does not exist any more.</p>
        <Button asChild variant="primary" className="mt-4">
          <Link to="/">Start a new chat</Link>
        </Button>
      </div>
    );
  }

  const panel = preview && (
    <PreviewPanel runId={preview.runId} tab={preview.tab} onTab={(tab) => setPreview({ ...preview, tab })} onClose={closePreview} />
  );

  return (
    <div className="flex h-full min-h-0">
      <section aria-label="Conversation" className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-line px-4 py-2">
          <h1 className="min-w-0 flex-1 truncate text-md font-semibold text-ink" title={chat?.title}>
            {chat?.title ?? "…"}
          </h1>
          {lastRun && <StatusBadge status={lastRun.status} />}
        </div>
        <ScrollArea className="min-h-0 flex-1" viewportClassName="px-4">
          <div className="mx-auto max-w-3xl space-y-8 py-5">
            {!chat && <p className="text-sm text-muted">Loading…</p>}
            {chat?.items.map((item, i) => (
              <Turn
                key={item.turn}
                chatId={chat.id}
                item={item}
                isLast={i === chat.items.length - 1}
                previewRunId={preview?.runId ?? null}
                onPreview={openPreview}
                onFollowUp={(q) => send.mutate(q)}
                onAnswered={refresh}
              />
            ))}
            <div ref={bottom} />
          </div>
        </ScrollArea>
        <div className="border-t border-line bg-canvas px-4 py-3">
          <div className="mx-auto max-w-3xl">
            <ChatBar
              value={text}
              onChange={setText}
              onSend={() => submit(text.trim())}
              sending={send.isPending || clarify.isPending}
              busy={busy}
              onStop={() => stop.mutate()}
              disabled={busy}
              label={awaiting ? "Your answer" : "Ask a follow-up question"}
              placeholder={awaiting ? "Answer the question above" : busy ? "Working on your question…" : "Ask a follow-up question"}
              options={options}
              onOptions={setOptions}
              footer={<OptionChips options={options} />}
            />
          </div>
        </div>
      </section>
      {isDesktop && panel && <aside className="w-[min(560px,46vw)] shrink-0 border-l border-line">{panel}</aside>}
      {!isDesktop && <Sheet open={Boolean(panel)} onOpenChange={(o) => !o && closePreview()} title="Preview" side="full">{panel}</Sheet>}
    </div>
  );
}
