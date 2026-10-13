import type { ComponentProps } from "react";
import { Tabs as T } from "radix-ui";
import { cn } from "./cn";

export const Tabs = T.Root;

export function TabsList({ className, ...props }: ComponentProps<typeof T.List>) {
  return <T.List className={cn("flex gap-1 overflow-x-auto border-b border-line px-3 pt-2", className)} {...props} />;
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      className={cn(
        "whitespace-nowrap border-b-2 border-transparent px-3 py-2 text-sm text-muted hover:text-ink",
        "data-[state=active]:border-brand-600 data-[state=active]:font-medium data-[state=active]:text-brand-700",
        className,
      )}
      {...props}
    />
  );
}

export const TabsContent = T.Content;
