import { useEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import type { MessageOptions } from "../lib/api";
import type { ProviderChoice } from "../lib/types";
import {
  Button,
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  cn,
} from "./ui";

const MODELS: { value: ProviderChoice; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Google Gemini" },
];

export function modelLabel(p: ProviderChoice): string {
  return MODELS.find((m) => m.value === p)?.label ?? p;
}

/** Chips for the options that differ from the defaults, shown under the bar. */
export function OptionChips({ options }: { options: MessageOptions }) {
  const chips = [options.webContext && "Web context on", options.provider !== "auto" && `Model: ${modelLabel(options.provider)}`].filter(Boolean);
  if (!chips.length) return null;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Options for the next question">
      {chips.map((c) => (
        <li key={String(c)} className="rounded-full border border-line bg-surface-sunken px-2.5 py-0.5 text-2xs text-muted">
          {c}
        </li>
      ))}
    </ul>
  );
}

/**
 * The rounded chat bar. "+" opens the options (web context, model); Enter sends, Shift+Enter adds a line;
 * while a run is going the send button becomes Stop.
 */
export default function ChatBar({
  value,
  onChange,
  onSend,
  placeholder,
  options,
  onOptions,
  busy = false,
  sending = false,
  onStop,
  disabled = false,
  autoFocus = false,
  label = "Ask a question",
  footer,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  placeholder: string;
  options: MessageOptions;
  onOptions: (o: MessageOptions) => void;
  /** A run is going: show Stop instead of Send. */
  busy?: boolean;
  sending?: boolean;
  onStop?: () => void;
  disabled?: boolean;
  autoFocus?: boolean;
  label?: string;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const canSend = !disabled && !sending && value.trim().length >= 3;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [value]);
  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (canSend) onSend();
    }
  };

  return (
    <div className="space-y-2">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (canSend) onSend();
        }}
        className={cn(
          "flex items-end gap-1.5 rounded-xl border border-line-strong bg-surface p-1.5 focus-within:border-brand-500",
          disabled && "opacity-70",
        )}
      >
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" aria-label="Options" className="h-9 w-9 shrink-0 rounded-full p-0 text-md">
              <span aria-hidden>＋</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" side="top" className="min-w-56">
            <DropdownMenuCheckboxItem
              checked={options.webContext}
              onCheckedChange={(c) => onOptions({ ...options, webContext: c === true })}
            >
              Include web context
            </DropdownMenuCheckboxItem>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Model</DropdownMenuLabel>
            <DropdownMenuRadioGroup value={options.provider} onValueChange={(v) => onOptions({ ...options, provider: v as ProviderChoice })}>
              {MODELS.map((m) => (
                <DropdownMenuRadioItem key={m.value} value={m.value}>
                  {m.label}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
        <textarea
          ref={ref}
          aria-label={label}
          rows={1}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          className="max-h-44 min-h-9 min-w-0 flex-1 resize-none bg-transparent px-1 py-2 text-base text-ink outline-none"
        />
        {busy ? (
          <Button variant="secondary" className="h-9 shrink-0 rounded-full px-4" onClick={onStop}>
            Stop
          </Button>
        ) : (
          <Button type="submit" variant="primary" className="h-9 shrink-0 rounded-full px-4" disabled={!canSend}>
            {sending ? "Sending…" : "Send"}
          </Button>
        )}
      </form>
      {footer}
    </div>
  );
}
