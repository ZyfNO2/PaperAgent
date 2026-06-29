// Session 52: 顶栏 — 项目名 + 当前 Session + 模式
import { APP_CONFIG } from "../../app/config";

export function TopBar() {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark">PA</span>
        <span className="brand-name">{APP_CONFIG.appName}</span>
        <span className="brand-tag">React 前端 · S52</span>
      </div>
      <div className="topbar-meta muted">
        mode: <code>{APP_CONFIG.mode}</code> · session:{" "}
        <code>S{APP_CONFIG.currentSession}</code>
      </div>
    </header>
  );
}
