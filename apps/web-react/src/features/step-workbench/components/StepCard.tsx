// Session 54: StepCard — 当前 step 主体内容 (result 摘要 + key/value 列表)
import type { StepState } from "../stepTypes";
import { Card } from "../../../components/ui/Card";
import { Button } from "../../../components/ui/Button";
import { STATUS_LABEL } from "../stepTypes";

interface Props {
  step: StepState;
  stepIndex: number;
  isPaused: boolean;
  onConfirm: () => void;
  onRevise: () => void;
  testId?: string;
}

export function StepCard({ step, stepIndex, isPaused, onConfirm, onRevise, testId }: Props) {
  return (
    <Card
      title={
        <span>
          Step {stepIndex + 1}: {step.title}
        </span>
      }
      testId={testId ?? "step-card"}
      footer={
        <div className="step-card__footer">
          <span className="pa-muted pa-small">状态: {STATUS_LABEL[step.status] ?? step.status}</span>
          {step.staleReason ? (
            <span className="pa-warn pa-small">stale: {step.staleReason}</span>
          ) : null}
          {isPaused ? (
            <div className="step-card__actions">
              <Button variant="primary" size="sm" onClick={onConfirm} data-testid="step-confirm">
                确认
              </Button>
              <Button variant="ghost" size="sm" onClick={onRevise} data-testid="step-revise">
                需要修改
              </Button>
            </div>
          ) : null}
        </div>
      }
    >
      {!step.result ? (
        <div className="pa-muted pa-small" data-testid="step-empty">
          等待用户输入, LLM 流式生成中...
        </div>
      ) : (
        <dl className="step-card__kv" data-testid="step-kv">
          {Object.entries(step.result).map(([k, v]) => (
            <div key={k} className="step-card__kv-row">
              <dt className="pa-muted pa-small">{k}</dt>
              <dd className="pa-small">{renderValue(v)}</dd>
            </div>
          ))}
        </dl>
      )}
    </Card>
  );
}

function renderValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  if (Array.isArray(v)) return v.map((x) => (typeof x === "string" ? x : JSON.stringify(x))).join(", ");
  return JSON.stringify(v);
}
