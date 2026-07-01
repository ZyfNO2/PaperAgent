// Session 53: MainStage — 中间主内容区
// 切换 step 时只是 children 变化, 不影响左右栏
import type { ReactNode } from "react";
import { Stepper } from "../ui/Stepper";

export interface StepperSpec {
  key: string;
  title: ReactNode;
  state?: "done" | "active" | "pending";
}

export interface MainStageProps {
  title: ReactNode;
  stepper?: StepperSpec[];
  children?: ReactNode;
  testId?: string;
}

export function MainStage({
  title,
  stepper,
  children,
  testId,
}: MainStageProps) {
  return (
    <main
      className="pa-main-stage"
      data-testid={testId ?? "main-stage"}
      aria-label="主内容区"
    >
      <header className="pa-main-stage__header">
        <h1 className="pa-main-stage__title pa-h1">{title}</h1>
        {stepper && stepper.length > 0 ? (
          <div className="pa-main-stage__stepper">
            <Stepper items={stepper} testId="main-stepper" />
          </div>
        ) : null}
      </header>
      <section className="pa-main-stage__body">{children}</section>
    </main>
  );
}
