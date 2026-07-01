// Session 53: Badge 组件 — 状态标签 (ok/warn/err/info/neutral)
import type { HTMLAttributes, ReactNode } from "react";

type Tone = "ok" | "warn" | "err" | "info" | "neutral";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
  children: ReactNode;
  testId?: string;
}

export function Badge({
  tone = "neutral",
  children,
  className,
  testId,
  ...rest
}: BadgeProps) {
  const cls = ["pa-badge", `pa-badge--${tone}`, className ?? ""]
    .filter(Boolean)
    .join(" ");
  return (
    <span
      className={cls}
      data-testid={testId ?? "badge"}
      {...rest}
    >
      {children}
    </span>
  );
}
