import type { ReactNode } from "react";
import { Dialog as D, VisuallyHidden } from "radix-ui";

/** Modal dialog. `title` is always rendered for screen readers; `hideTitle` makes it visually hidden. */
export function Modal({
  open,
  onOpenChange,
  title,
  hideTitle,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  hideTitle?: boolean;
  children: ReactNode;
}) {
  const heading = <D.Title className="text-base font-semibold text-ink">{title}</D.Title>;
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-40 bg-slate-900/50 data-[state=open]:animate-overlay-in data-[state=closed]:animate-overlay-out" />
        <D.Content
          aria-describedby={undefined}
          className="fixed left-1/2 top-1/2 z-50 max-h-[92vh] w-[calc(100%-2rem)] max-w-5xl -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-xl bg-surface p-4 shadow-xl data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out"
        >
          <div className="mb-2 flex items-start justify-between gap-3">
            {hideTitle ? <VisuallyHidden.Root asChild>{heading}</VisuallyHidden.Root> : heading}
            <D.Close
              aria-label="Close"
              className="ml-auto rounded-md px-2 py-0.5 text-lg leading-none text-muted hover:bg-surface-sunken hover:text-ink"
            >
              <span aria-hidden>×</span>
            </D.Close>
          </div>
          {children}
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}
