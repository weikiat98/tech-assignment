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
          "z-50 min-w-40 rounded-lg border border-line bg-surface p-1 shadow-float",
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
          ? "text-danger data-[highlighted]:bg-danger-bg"
          : "text-ink data-[highlighted]:bg-brand-50 data-[highlighted]:text-brand-700 focus-visible:outline-none",
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

const ITEM =
  "relative flex cursor-pointer select-none items-center gap-2 rounded-md py-1.5 pl-7 pr-2.5 text-sm text-ink outline-none " +
  "data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-brand-50 data-[highlighted]:text-brand-700";

/**
 * The tick for a checked item. The indicator is positioned out of the flex row, so the label stays put whether
 * the item is checked or not, and it is centred on the row's height.
 */
const Tick = () => (
  <D.ItemIndicator className="absolute inset-y-0 left-2 flex w-4 items-center justify-center" aria-hidden>
    ✓
  </D.ItemIndicator>
);

export function DropdownMenuCheckboxItem({ children, className, ...props }: ComponentProps<typeof D.CheckboxItem>) {
  return (
    <D.CheckboxItem className={cn(ITEM, className)} {...props}>
      <Tick />
      {children}
    </D.CheckboxItem>
  );
}

export const DropdownMenuRadioGroup = D.RadioGroup;

export function DropdownMenuRadioItem({ children, className, ...props }: ComponentProps<typeof D.RadioItem>) {
  return (
    <D.RadioItem className={cn(ITEM, className)} {...props}>
      <Tick />
      {children}
    </D.RadioItem>
  );
}

export function DropdownMenuLabel({ className, ...props }: ComponentProps<typeof D.Label>) {
  return <D.Label className={cn("px-2.5 pb-1 pt-1.5 text-2xs font-medium text-muted", className)} {...props} />;
}
