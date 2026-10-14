import { useEffect, useRef } from "react";
import { useToast } from "../components/ui";
import type { AgentEvent } from "./types";

/**
 * Toasts for notable live events (fallbacks, failed drafts, errors, the final status). Everything up to
 * `liveAfter` is the history replayed when the page opened, so it never toasts; this compares sequence
 * numbers, not the browser and server clocks.
 */
export function useRunToasts(events: AgentEvent[], liveAfter: number | null) {
  const toast = useToast();
  const toasted = useRef(0);
  useEffect(() => {
    if (liveAfter === null) return;
    for (const e of events) {
      if (e.seq <= toasted.current) continue;
      toasted.current = e.seq;
      if (e.seq <= liveAfter) continue;
      const c = e.content;
      if (e.type === "fallback") {
        toast({
          title: c.kind === "llm" ? `LLM fallback: ${c.from} → ${c.to}` : "Source fallback",
          description: c.kind === "llm" ? c.task : String(c.dataset ?? c.source ?? c.kind ?? ""),
          tone: "warning",
        });
      } else if (e.type === "verification" && c.passed === false) {
        toast({ title: "Draft failed verification", description: `Rewriting (attempt ${c.attempt})`, tone: "warning" });
      } else if (e.type === "error") {
        toast({ title: "Run error", description: String(c.message ?? ""), tone: "error" });
      } else if (e.type === "final") {
        toast({ title: `Analysis ${c.status}`, tone: c.status === "completed" ? "success" : "warning" });
      }
    }
  }, [events, liveAfter, toast]);
}
