// Session 59: SideNav 极简化 — 普通用户模式下不渲染任何分组, 仅保留 dev 入口占位.
// 高级导航 (工作流/评估/协议/系统) 已迁入 DeveloperPanel.

interface Props {
  currentMode?: string;
}

export function SideNav(_props: Props) {
  // ponytail: 普通用户不应看到 docs rail, 直接返回空容器保留 grid 占位.
  return (
    <nav className="pa-sidenav pa-sidenav--empty" data-testid="sidenav" aria-hidden="true" />
  );
}