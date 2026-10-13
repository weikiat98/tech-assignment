import type { ReactNode } from "react";
import { AlertDialog as A } from "radix-ui";
import { Button } from "./button";

/** Confirm dialog. Focus starts on Cancel; Esc or an outside click cancels, never confirms. */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Delete",
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
}) {
  return (
    <A.Root open={open} onOpenChange={onOpenChange}>
      <A.Portal>
        <A.Overlay className="fixed inset-0 z-40 bg-slate-900/40 data-[state=open]:animate-overlay-in data-[state=closed]:animate-overlay-out" />
        <A.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-xl bg-surface p-5 shadow-xl data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out">
          <A.Title className="text-base font-semibold text-ink">{title}</A.Title>
          <A.Description className="mt-2 text-sm text-muted">{description}</A.Description>
          <div className="mt-5 flex justify-end gap-2">
            <A.Cancel asChild>
              <Button>Cancel</Button>
            </A.Cancel>
            <A.Action asChild>
              <Button variant="danger" onClick={onConfirm}>
                {confirmLabel}
              </Button>
            </A.Action>
          </div>
        </A.Content>
      </A.Portal>
    </A.Root>
  );
}
