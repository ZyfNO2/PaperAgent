// Session 52: Shell 页面 — 三栏布局占位
import type { ReactNode } from "react";

interface Props {
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
}

export function Shell({ left, center, right }: Props) {
  return (
    <div className="shell">
      <div className="shell-left">{left}</div>
      <div className="shell-center">{center}</div>
      <div className="shell-right">{right}</div>
    </div>
  );
}
