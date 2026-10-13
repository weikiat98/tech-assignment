import type { ComponentProps, ReactNode } from "react";
import { DropdownMenu as D } from "radix-ui";
import { cn } from "./cn";

export const DropdownMenu = D.Root;
export const DropdownMenuTrigger = D.Trigger;

export function DropdownMenuContent({ className, children, ...props }: ComponentProps<typeof D.Content>) {
  return (
    <D.Portal>
      <D.Content
        align="end"
        sideOffset={6}
        collisionPadding={8}
        className={cn(
          "z-50 min-w-40 rounded-lg border border-line bg-surface p-1 shadow-lg",
          "data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out",
          className,
        )}
        {...props}
      >
        {children}
      </D.Content>
    </D.Portal>
  );
}

export function DropdownMenuItem({
  className,
  icon,
  tone,
  children,
  asChild,
  ...props
}: { icon?: ReactNode; tone?: "danger" } & ComponentProps<typeof D.Item>) {
  return (
    <D.Item
      className={cn(
        "flex cursor-pointer select-none items-center gap-2 rounded-md px-2.5 py-1.5 text-sm outline-none",
        "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        tone === "danger"
          ? "text-red-700 data-[highlighted]:bg-red-50"
          : "text-ink data-[highlighted]:bg-brand-50 data-[highlighted]:text-brand-700",
        className,
      )}
      asChild={asChild}
      {...props}
    >
      {/* With asChild, Radix's Slot needs exactly one child element, so the icon can't sit beside it. */}
      {asChild ? (
        children
      ) : (
        <>
          {icon}
          {children}
        </>
      )}
    </D.Item>
  );
}

export const DropdownMenuSeparator = ({ className }: { className?: string }) => (
  <D.Separator className={cn("my-1 h-px bg-line", className)} />
);
