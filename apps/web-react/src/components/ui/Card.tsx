// Session 53: Card 组件 — 工具型, 不超过 8px 圆角
import type { HTMLAttributes, ReactNode } from "react";

export interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title?: ReactNode;
  footer?: ReactNode;
  children?: ReactNode;
  testId?: string;
}

export function Card({
  title,
  footer,
  children,
  className,
  testId,
  ...rest
}: CardProps) {
  const cls = ["pa-card", className ?? ""].filter(Boolean).join(" ");
  return (
    <div
      className={cls}
      data-testid={testId ?? "card"}
      {...rest}
    >
      {title ? <div className="pa-card__title">{title}</div> : null}
      <div className="pa-card__body">{children}</div>
      {footer ? <div className="pa-card__footer">{footer}</div> : null}
    </div>
  );
}
