// Session 53: Stepper 组件 — 步骤指示器 (done/active/pending)
import type { ReactNode } from "react";

export interface StepperItem {
  key: string;
  title: ReactNode;
  state?: "done" | "active" | "pending";
}

export interface StepperProps {
  items: StepperItem[];
  testId?: string;
}

export function Stepper({ items, testId }: StepperProps) {
  return (
    <ol className="pa-stepper" data-testid={testId ?? "stepper"}>
      {items.map((it, idx) => {
        const state = it.state ?? "pending";
        return (
          <li
            key={it.key}
            className={`pa-stepper__item pa-stepper__item--${state}`}
            data-testid={`step-${it.key}`}
            data-state={state}
          >
            <span className="pa-stepper__idx">{idx + 1}</span>
            <span className="pa-stepper__title">{it.title}</span>
          </li>
        );
      })}
    </ol>
  );
}
