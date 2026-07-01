// Session 53: WorkbenchShell — 三栏工作台
// 中间 (MainStage) children 切换时, 左右栏不 unmount
// Session 59: 加上 DeveloperPanel — 开发者抽屉在所有路由可用 (Ctrl+` 触发)
import type { ReactNode } from "react";
import { TopBar } from "./TopBar";
import { DeveloperPanel } from "../dev/DeveloperPanel";

export interface WorkbenchShellProps {
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
  testId?: string;
}

export function WorkbenchShell({ left, center, right, testId }: WorkbenchShellProps) {
  return (
    <div className="pa-app-root" data-testid={testId ?? "workbench-shell"}>
      <TopBar />
      <div
        className="pa-workbench"
        data-testid="workbench-grid"
        style={{
          gridTemplateColumns:
            "var(--pa-shell-left) minmax(0, 1fr) var(--pa-shell-right)",
        }}
      >
        <div
          className="pa-workbench__col pa-workbench__col--left"
          data-testid="workbench-left"
        >
          {left}
        </div>
        <div
          className="pa-workbench__col pa-workbench__col--center"
          data-testid="workbench-center"
        >
          {center}
        </div>
        <div
          className="pa-workbench__col pa-workbench__col--right"
          data-testid="workbench-right"
        >
          {right}
        </div>
      </div>
      <DeveloperPanel />
    </div>
  );
}
