import { useCallback, useState } from "react";
import type { MessageOptions } from "./api";

const KEY = "owl-message-options";
const DEFAULTS: MessageOptions = { webContext: false, provider: "auto" };

function read(): MessageOptions {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (raw && typeof raw.webContext === "boolean" && ["auto", "openai", "gemini"].includes(raw.provider)) return raw;
  } catch {
    /* unreadable: use the defaults */
  }
  return DEFAULTS;
}

/** Web context and model choice for the next question; remembered per browser. */
export function useMessageOptions(): [MessageOptions, (next: MessageOptions) => void] {
  const [options, setOptions] = useState<MessageOptions>(read);
  const update = useCallback((next: MessageOptions) => {
    setOptions(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* storage unavailable: the choice lasts for this page only */
    }
  }, []);
  return [options, update];
}
