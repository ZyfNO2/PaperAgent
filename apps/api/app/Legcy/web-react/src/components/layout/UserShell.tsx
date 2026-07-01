// Session 59: UserShell — 极简主工作台 (无三栏), 自上而下 4 区.
// 主题: paperagent 极简主流程; 高级内容全部进 DeveloperPanel 抽屉.
import type { ReactNode } from "react";
import { TopBar } from "./TopBar";
import { DeveloperPanel } from "../dev/DeveloperPanel";

export interface UserShellProps {
  children: ReactNode;
  testId?: string;
}

export function UserShell({ children, testId }: UserShellProps) {
  return (
    <div className="pa-app-root" data-testid={testId ?? "user-shell"}>
      <TopBar />
      <div className="pa-user-main" data-testid="user-main">
        {children}
      </div>
      <DeveloperPanel />
    </div>
  );
}