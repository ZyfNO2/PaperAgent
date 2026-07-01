// Session 54: StepGate — 暂停确认时显示的 Gate 提示
import { Badge } from "../../../components/ui/Badge";

interface Props {
  open: boolean;
  stepTitle: string;
  testId?: string;
}

export function StepGate({ open, stepTitle, testId }: Props) {
  if (!open) return null;
  return (
    <div
      className="pa-step-gate"
      role="status"
      aria-live="polite"
      data-testid={testId ?? "step-gate"}
    >
      <Badge tone="warn" testId="gate-badge">Gate</Badge>
      <span className="pa-small">
        <strong>{stepTitle}</strong> 已暂停, 等待用户确认后再继续。
      </span>
    </div>
  );
}
