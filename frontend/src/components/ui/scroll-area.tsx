import type { ComponentProps, ReactNode } from "react";
import { ScrollArea as S } from "radix-ui";
import { cn } from "./cn";

/**
 * Custom scrollbars over native scrolling. Uses the `Content` pattern: `disableImplicitContentElement`
 * stops Viewport rendering its own (deprecated) wrapper, so our `Content` is the only measured element.
 */
export function ScrollArea({
  children,
  className,
  viewportClassName,
  ...props
}: { children: ReactNode; viewportClassName?: string } & ComponentProps<typeof S.Root>) {
  return (
    <S.Root type="auto" className={cn("relative overflow-hidden", className)} {...props}>
      <S.Viewport disableImplicitContentElement className={cn("h-full w-full rounded-[inherit]", viewportClassName)}>
        {/* Content defaults to display:table, which lets long lines widen it and forces a horizontal scrollbar. */}
        <S.Content style={{ display: "block" }}>{children}</S.Content>
      </S.Viewport>
      <S.Scrollbar orientation="vertical" className="flex w-2 touch-none select-none p-0.5 transition-colors hover:bg-surface-sunken">
        <S.Thumb className="relative flex-1 rounded-full bg-line-strong" />
      </S.Scrollbar>
      <S.Scrollbar orientation="horizontal" className="flex h-2 touch-none select-none flex-col p-0.5 hover:bg-surface-sunken">
        <S.Thumb className="relative flex-1 rounded-full bg-line-strong" />
      </S.Scrollbar>
      <S.Corner />
    </S.Root>
  );
}
