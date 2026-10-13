import type { ComponentProps } from "react";
import { ToggleGroup as G } from "radix-ui";
import { cn } from "./cn";

export const ToggleGroup = G.Root;

/** Pill-style toggle; `data-state=on` marks the selected value. */
export function ToggleGroupItem({ className, ...props }: ComponentProps<typeof G.Item>) {
  return (
    <G.Item
      className={cn(
        "rounded-full border border-line bg-surface px-2.5 py-0.5 text-[11px] text-muted hover:border-line-strong",
        "data-[state=on]:border-brand-500 data-[state=on]:bg-brand-50 data-[state=on]:font-medium data-[state=on]:text-brand-700",
        className,
      )}
      {...props}
    />
  );
}
