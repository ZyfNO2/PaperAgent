// Session 54: StepNavigator — 5 步横向切换 + 状态色
import { STATUS_LABEL, type StepState } from "../stepTypes";
import { Badge } from "../../../components/ui/Badge";

interface Props {
  steps: StepState[];
  activeIndex: number;
  onSelect: (idx: number) => void;
  testId?: string;
}

export function StepNavigator({ steps, activeIndex, onSelect, testId }: Props) {
  return (
    <ol className="pa-stepper pa-stepper--nav" data-testid={testId ?? "step-nav"}>
      {steps.map((s, idx) => {
        const state =
          idx === activeIndex
            ? "active"
            : s.status === "completed" || s.status === "approved"
              ? "done"
              : "pending";
        return (
          <li
            key={s.key}
            className={`pa-stepper__item pa-stepper__item--${state}`}
            data-testid={`step-nav-${s.key}`}
            data-state={s.status}
          >
            <button
              type="button"
              className="pa-stepper__btn"
              onClick={() => onSelect(idx)}
              aria-current={idx === activeIndex ? "step" : undefined}
            >
              <span className="pa-stepper__idx">{s.icon || idx + 1}</span>
              <span className="pa-stepper__title">{s.title}</span>
              <Badge tone={state === "done" ? "ok" : state === "active" ? "info" : "neutral"} testId={`step-badge-${s.key}`}>
                {STATUS_LABEL[s.status] ?? s.status}
              </Badge>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
