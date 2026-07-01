// Session 53: Button 组件 — variants: primary/secondary/ghost/danger; sizes: sm/md
// 状态: default/loading/disabled, 都有 data-testid
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

export interface ButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  testId?: string;
  children: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  disabled,
  children,
  className,
  testId,
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;
  const cls = [
    "pa-btn",
    `pa-btn--${variant}`,
    `pa-btn--${size}`,
    loading ? "pa-btn--loading" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      className={cls}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      data-testid={testId ?? "button"}
      {...rest}
    >
      {loading ? <span className="pa-btn__spinner" aria-hidden="true" /> : null}
      <span className="pa-btn__label">{children}</span>
    </button>
  );
}
