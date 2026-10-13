import type { ComponentProps, ReactNode } from "react";
import { Collapsible as C } from "radix-ui";
import { cn } from "./cn";

export const Collapsible = C.Root;

/** Keyboard-operable trigger (a real button, `aria-expanded` from Radix). */
export function CollapsibleTrigger({ className, ...props }: ComponentProps<typeof C.Trigger>) {
  return <C.Trigger className={cn("text-left", className)} {...props} />;
}

/** Height animates through --radix-collapsible-content-height. */
export function CollapsibleContent({ className, children, ...props }: ComponentProps<typeof C.Content> & { children: ReactNode }) {
  return (
    <C.Content
      className={cn("overflow-hidden data-[state=open]:animate-expand data-[state=closed]:animate-collapse", className)}
      {...props}
    >
      {children}
    </C.Content>
  );
}
