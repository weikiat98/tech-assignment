import { useId, type ComponentProps } from "react";
import { Label, Switch as S } from "radix-ui";
import { cn } from "./cn";

/** Labelled on/off switch. `tone="danger"` is for chaos toggles (red when on). */
export function Switch({
  label,
  tone = "brand",
  className,
  ...props
}: { label: string; tone?: "brand" | "danger" } & ComponentProps<typeof S.Root>) {
  const id = useId();
  return (
    <div className={cn("flex items-center justify-between gap-2", className)}>
      <Label.Root htmlFor={id} className="cursor-pointer text-sm text-ink">
        {label}
      </Label.Root>
      <S.Root
        id={id}
        className={cn(
          "relative h-5 w-9 shrink-0 rounded-full bg-line-strong transition-colors",
          tone === "danger" ? "data-[state=checked]:bg-danger" : "data-[state=checked]:bg-brand-600",
        )}
        {...props}
      >
        <S.Thumb className="block h-4 w-4 translate-x-0.5 rounded-full bg-ink transition-transform data-[state=checked]:translate-x-[18px]" />
      </S.Root>
    </div>
  );
}

/** Compact switch with the label on the right (form options, filters). */
export function InlineSwitch({ label, ...props }: { label: string } & ComponentProps<typeof S.Root>) {
  const id = useId();
  return (
    <div className="flex items-center gap-2">
      <S.Root
        id={id}
        className="relative h-4 w-7 shrink-0 rounded-full bg-line-strong transition-colors data-[state=checked]:bg-brand-600"
        {...props}
      >
        <S.Thumb className="block h-3 w-3 translate-x-0.5 rounded-full bg-ink transition-transform data-[state=checked]:translate-x-[14px]" />
      </S.Root>
      <Label.Root htmlFor={id} className="cursor-pointer text-sm text-muted">
        {label}
      </Label.Root>
    </div>
  );
}
