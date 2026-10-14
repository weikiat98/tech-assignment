import type { ComponentProps, ReactNode } from "react";
import { Tooltip as T } from "radix-ui";
import { cn } from "./cn";

export const TooltipProvider = T.Provider;

/** Wraps a single focusable trigger; content is portalled so scrolling containers never clip it. */
export function Tooltip({
  trigger,
  children,
  className,
  ...props
}: { trigger: ReactNode; children: ReactNode } & Omit<ComponentProps<typeof T.Content>, "children">) {
  return (
    <T.Root>
      <T.Trigger asChild>{trigger}</T.Trigger>
      <T.Portal>
        <T.Content
          sideOffset={6}
          collisionPadding={8}
          className={cn(
            "z-50 max-w-72 rounded-lg border border-line-strong bg-surface-sunken px-2.5 py-2 text-xs font-normal text-ink shadow-float",
            "data-[state=delayed-open]:animate-pop-in data-[state=instant-open]:animate-pop-in data-[state=closed]:animate-pop-out",
            className,
          )}
          {...props}
        >
          {children}
          <T.Arrow className="fill-surface-sunken" />
        </T.Content>
      </T.Portal>
    </T.Root>
  );
}
