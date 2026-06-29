// Session 59: TopBar 极简化 — 普通用户只看到 paperagent wordmark + 开发者按钮
// 高级入口 (RAG/ThesisEval/面试/协议/旧前端) 全部迁入开发者窗口.
import { useEffect, useState } from "react";

const STORAGE_KEY = "paperagent:dev-mode";

function isDevOpen(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(STORAGE_KEY) === "1";
}

function setDevOpen(open: boolean): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, open ? "1" : "0");
  window.dispatchEvent(new CustomEvent("paperagent:dev-mode", { detail: open }));
}

export function TopBar() {
  // ponytail: dev-state 走 storage + 自定义事件, 不引 context / store
  const [devOpen, setLocalDevOpen] = useState<boolean>(() => isDevOpen());

  useEffect(() => {
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent<boolean>).detail;
      setLocalDevOpen(Boolean(detail));
    };
    window.addEventListener("paperagent:dev-mode", onChange);
    return () => window.removeEventListener("paperagent:dev-mode", onChange);
  }, []);

  const toggle = () => {
    const next = !devOpen;
    setDevOpen(next);
    setLocalDevOpen(next);
  };

  return (
    <header className="pa-topbar pa-topbar--minimal" data-testid="topbar">
      <div className="pa-topbar__brand">
        <span className="pa-topbar__mark" aria-hidden>pa</span>
        <span className="pa-topbar__name">paperagent</span>
      </div>
      <div className="pa-topbar__actions">
        <button
          type="button"
          className={
            "pa-topbar__dev-toggle" + (devOpen ? " pa-topbar__dev-toggle--on" : "")
          }
          onClick={toggle}
          aria-pressed={devOpen}
          title="切换开发者窗口 (Ctrl + `)"
          data-testid="topbar-dev-toggle"
        >
          {devOpen ? "关闭开发者" : "开发者"}
          <span className="pa-topbar__kbd" aria-hidden>⌃`</span>
        </button>
      </div>
    </header>
  );
}

export const DEV_MODE_STORAGE_KEY = STORAGE_KEY;
export const openDevMode = () => setDevOpen(true);
export const closeDevMode = () => setDevOpen(false);
export const isDevModeOpen = isDevOpen;