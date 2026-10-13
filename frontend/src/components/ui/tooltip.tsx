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
            "z-50 max-w-72 rounded-lg bg-slate-900 p-2 text-[11px] font-normal leading-snug text-white shadow-lg",
            "data-[state=delayed-open]:animate-pop-in data-[state=instant-open]:animate-pop-in data-[state=closed]:animate-pop-out",
            className,
          )}
          {...props}
        >
          {children}
          <T.Arrow className="fill-slate-900" />
        </T.Content>
      </T.Portal>
    </T.Root>
  );
}
