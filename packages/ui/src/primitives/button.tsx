import { forwardRef, type ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-brand text-surface border-transparent",
  secondary: "bg-surface text-ink border-hairline",
  ghost: "bg-transparent text-brand border-transparent hover:bg-brand-tint",
  danger: "bg-danger text-surface border-transparent",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", className = "", disabled, ...props },
  ref
) {
  return (
    <button
      ref={ref}
      disabled={disabled}
      className={[
        "inline-flex items-center justify-center rounded-md border px-4 py-2 text-sm font-medium",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        VARIANT_CLASSES[variant],
        className,
      ].join(" ")}
      {...props}
    />
  );
});
