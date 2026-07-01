// Session 53: Spinner 组件 — loading 状态
export interface SpinnerProps {
  size?: number;
  label?: string;
  testId?: string;
}

export function Spinner({ size = 14, label, testId }: SpinnerProps) {
  return (
    <span
      className="pa-spinner"
      role="status"
      aria-label={label ?? "loading"}
      data-testid={testId ?? "spinner"}
      style={{ width: size, height: size }}
    />
  );
}
