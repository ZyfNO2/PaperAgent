// Session 53: ErrorState 组件 — 错误/空/降级展示
import type { ReactNode } from "react";
import { Button } from "./Button";

export interface ErrorStateProps {
  title?: ReactNode;
  message?: ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
  testId?: string;
}

export function ErrorState({
  title = "出错了",
  message,
  onRetry,
  retryLabel = "重试",
  testId,
}: ErrorStateProps) {
  return (
    <div
      className="pa-error-state"
      role="alert"
      data-testid={testId ?? "error-state"}
    >
      <div className="pa-error-state__title">{title}</div>
      {message ? (
        <div className="pa-error-state__message pa-muted">{message}</div>
      ) : null}
      {onRetry ? (
        <Button
          variant="primary"
          size="sm"
          onClick={onRetry}
          data-testid="error-retry"
        >
          {retryLabel}
        </Button>
      ) : null}
    </div>
  );
}
