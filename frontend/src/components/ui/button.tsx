import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Slot } from "radix-ui/slot";
import { cn } from "./cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand-600 text-on-brand hover:bg-brand-700",
  secondary: "border border-line-strong bg-surface text-ink hover:border-brand-500",
  ghost: "text-muted hover:bg-surface-sunken hover:text-ink",
  danger: "bg-danger text-on-brand hover:brightness-110",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
  /** Render the child element (e.g. an <a>) with button styling instead of a <button>. */
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", asChild, className, type, ...props },
  ref,
) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      ref={ref}
      type={asChild ? undefined : (type ?? "button")}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
        size === "sm" ? "px-2.5 py-1 text-xs" : "px-3.5 py-1.5 text-sm",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
});
