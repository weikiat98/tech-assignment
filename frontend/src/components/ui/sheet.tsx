import type { ReactNode } from "react";
import { Dialog as D, VisuallyHidden } from "radix-ui";
import { cn } from "./cn";

/**
 * A modal panel that slides in from a side: the phone sidebar drawer (`left`) and the full-screen preview
 * (`full`). Same focus trap, Esc and overlay behaviour as Modal; the title is always present for screen readers.
 */
export function Sheet({
  open,
  onOpenChange,
  title,
  side = "left",
  children,
  className,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  side?: "left" | "full";
  children: ReactNode;
  className?: string;
}) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-40 bg-black/60 data-[state=open]:animate-overlay-in data-[state=closed]:animate-overlay-out" />
        <D.Content
          aria-describedby={undefined}
          className={cn(
            "fixed z-50 flex flex-col border-line bg-surface shadow-float data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out",
            side === "left" ? "inset-y-0 left-0 w-[min(320px,88vw)] border-r" : "inset-0",
            className,
          )}
        >
          <VisuallyHidden.Root asChild>
            <D.Title>{title}</D.Title>
          </VisuallyHidden.Root>
          {children}
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

export const SheetClose = D.Close;
