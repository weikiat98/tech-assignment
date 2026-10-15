import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, useMatch, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { groupChats } from "../lib/chats";
import type { ChatSummary } from "../lib/types";
import {
  Button,
  ConfirmDialog,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  ScrollArea,
  cn,
  useToast,
} from "./ui";

const useDebounced = (value: string, ms = 250) => {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
};

/** Chat list: search, groups by day, pin / rename in place / delete with confirmation (todo.md CL6). */
export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const [q, setQ] = useState("");
  const query = useDebounced(q.trim());
  const [renaming, setRenaming] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<ChatSummary | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const open = useMatch("/chats/:id")?.params.id;
  const { data, isLoading, error } = useQuery({
    queryKey: ["chats", query],
    queryFn: () => api.listChats(query || undefined),
    refetchInterval: (s) => (s.state.data?.some((c) => c.status === "running" || c.status === "queued") ? 4000 : false),
  });
  const groups = useMemo(() => groupChats(data ?? []), [data]);
  const refresh = () => qc.invalidateQueries({ queryKey: ["chats"] });
  const fail = (title: string) => (e: unknown) => toast({ title, description: (e as Error).message, tone: "error" });

  const pin = useMutation({ mutationFn: (c: ChatSummary) => api.pinChat(c.id, !c.pinned), onSuccess: refresh, onError: fail("Could not pin the chat") });
  const rename = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => api.renameChat(id, title),
    onSuccess: refresh,
    onError: fail("Could not rename the chat"),
  });
  const remove = useMutation({
    mutationFn: (c: ChatSummary) => api.deleteChat(c.id),
    onSuccess: (_, c) => {
      refresh();
      toast({ title: "Chat deleted", tone: "success" });
      if (open === c.id) navigate("/");
    },
    onError: fail("Could not delete the chat"),
  });

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="space-y-2 p-3">
        <Button variant="primary" className="w-full" onClick={() => { navigate("/"); onNavigate?.(); }}>
          <span aria-hidden>＋</span> New chat
        </Button>
        <input
          type="search"
          aria-label="Search chats"
          placeholder="Search chats"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="w-full rounded-md border border-line-strong bg-canvas px-2.5 py-1.5 text-sm text-ink"
        />
      </div>
      <ScrollArea className="min-h-0 flex-1" viewportClassName="px-2 pb-3">
        <nav aria-label="Chats">
          {isLoading && <p className="px-2 py-3 text-sm text-muted">Loading…</p>}
          {error && <p role="alert" className="px-2 py-3 text-sm text-danger">Could not load chats.</p>}
          {data && data.length === 0 && (
            <p className="px-2 py-6 text-center text-sm text-muted">{query ? "No chats match your search." : "No chats yet. Ask a question to start one."}</p>
          )}
          {groups.map((g) => (
            <section key={g.label} aria-label={g.label} className="mb-3">
              <h2 className="px-2 pb-1 text-2xs font-medium text-muted">{g.label}</h2>
              <ul>
                {g.chats.map((c) => (
                  <li key={c.id}>
                    {renaming === c.id ? (
                      <RenameField
                        initial={c.title}
                        onDone={(title) => {
                          setRenaming(null);
                          if (title && title !== c.title) rename.mutate({ id: c.id, title });
                        }}
                      />
                    ) : (
                      <div className={cn("group flex items-center rounded-md", open === c.id ? "bg-brand-50" : "hover:bg-surface-sunken")}>
                        <NavLink
                          to={`/chats/${c.id}`}
                          onClick={onNavigate}
                          aria-current={open === c.id ? "page" : undefined}
                          className={cn("min-w-0 flex-1 truncate rounded-md px-2 py-1.5 text-sm", open === c.id ? "font-medium text-brand-700" : "text-ink")}
                          title={c.title}
                        >
                          {c.pinned && <span className="mr-1 text-muted" aria-label="Pinned">📌</span>}
                          {c.title}
                          {(c.status === "running" || c.status === "queued") && <span className="ml-1.5 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-run align-middle" aria-label="Running" />}
                        </NavLink>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button size="sm" variant="ghost" aria-label={`Actions for ${c.title}`} className="shrink-0 opacity-70 focus-visible:opacity-100 group-hover:opacity-100">
                              <span aria-hidden>⋯</span>
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent>
                            <DropdownMenuItem onSelect={() => pin.mutate(c)}>{c.pinned ? "Unpin" : "Pin"}</DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => setRenaming(c.id)}>Rename</DropdownMenuItem>
                            <DropdownMenuItem tone="danger" onSelect={() => setPendingDelete(c)}>
                              Delete…
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </nav>
      </ScrollArea>
      <div className="border-t border-line p-2">
        <NavLink
          to="/activity"
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2.5 rounded-md px-2 py-2 text-sm",
              isActive ? "bg-brand-50 font-medium text-brand-700" : "text-muted hover:bg-surface-sunken hover:text-ink",
            )
          }
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
            <path d="M3 12h4l3 8 4-16 3 8h4" />
          </svg>
          Run activity
        </NavLink>
      </div>
      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(o) => !o && setPendingDelete(null)}
        title="Delete this chat?"
        description={<>“{pendingDelete?.title}” and every answer, chart and event in it will be removed. This can't be undone.</>}
        onConfirm={() => {
          if (pendingDelete) remove.mutate(pendingDelete);
          setPendingDelete(null);
        }}
      />
    </div>
  );
}

/** Edits a title in place: Enter or leaving the field saves, Esc cancels. */
function RenameField({ initial, onDone }: { initial: string; onDone: (title: string | null) => void }) {
  const [value, setValue] = useState(initial);
  const input = useRef<HTMLInputElement>(null);
  const finished = useRef(false);
  useEffect(() => {
    input.current?.focus();
    input.current?.select();
  }, []);
  const finish = (save: boolean) => {
    if (finished.current) return;
    finished.current = true;
    onDone(save ? value.trim() : null);
  };
  return (
    <input
      ref={input}
      aria-label="Chat title"
      maxLength={200}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => finish(true)}
      onKeyDown={(e) => {
        if (e.key === "Enter") finish(true);
        if (e.key === "Escape") finish(false);
      }}
      className="w-full rounded-md border border-brand-500 bg-canvas px-2 py-1.5 text-sm text-ink"
    />
  );
}
