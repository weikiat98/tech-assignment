import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { Toast as T } from "radix-ui";
import { cn } from "./cn";

type Tone = "info" | "success" | "warning" | "error";

export interface ToastInput {
  title: string;
  description?: string;
  tone?: Tone;
  /** Milliseconds before auto-dismiss. */
  duration?: number;
}

interface ToastItem extends ToastInput {
  id: number;
}

const TONES: Record<Tone, string> = {
  info: "border-line bg-surface",
  success: "border-ok/40 bg-ok-bg",
  warning: "border-warn/40 bg-warn-bg",
  error: "border-danger/40 bg-danger-bg",
};

const ToastContext = createContext<(t: ToastInput) => void>(() => {});

/** `const toast = useToast(); toast({ title: "...", tone: "error" })` */
export function useToast() {
  return useContext(ToastContext);
}

let nextId = 1;
const MAX_TOASTS = 4;

/** Mount once near the root. Radix announces toasts via aria-live; F8 focuses the viewport. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((t: ToastInput) => {
    setItems((prev) => [...prev, { ...t, id: nextId++ }].slice(-MAX_TOASTS));
  }, []);
  const remove = (id: number) => setItems((prev) => prev.filter((i) => i.id !== id));
  const value = useMemo(() => push, [push]);

  return (
    <ToastContext.Provider value={value}>
      <T.Provider swipeDirection="right" duration={5000} label="Notifications">
        {children}
        {items.map((i) => (
          <T.Root
            key={i.id}
            type={i.tone === "error" || i.tone === "warning" ? "foreground" : "background"}
            duration={i.duration}
            onOpenChange={(open) => !open && remove(i.id)}
            className={cn(
              "flex items-start gap-3 rounded-xl border p-3 shadow-float",
              "data-[state=open]:animate-toast-in data-[state=closed]:animate-toast-out",
              TONES[i.tone ?? "info"],
            )}
          >
            <div className="min-w-0 flex-1">
              <T.Title className="text-sm font-medium text-ink">{i.title}</T.Title>
              {i.description && (
                <T.Description className="mt-0.5 break-words text-xs text-muted">{i.description}</T.Description>
              )}
            </div>
            <T.Close aria-label="Dismiss notification" className="rounded px-1 text-muted hover:text-ink">
              <span aria-hidden>×</span>
            </T.Close>
          </T.Root>
        ))}
        <T.Viewport className="fixed bottom-4 right-4 z-[60] flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2 outline-none" />
      </T.Provider>
    </ToastContext.Provider>
  );
}
