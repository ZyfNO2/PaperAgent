// Session 53: TopBar — 项目名 + 当前 Session + 模式
import { APP_CONFIG } from "../../app/config";

export function TopBar() {
  return (
    <header className="pa-topbar" data-testid="topbar">
      <div className="pa-topbar__brand">
        <span className="pa-topbar__mark">PA</span>
        <span className="pa-topbar__name">{APP_CONFIG.appName}</span>
        <span className="pa-topbar__tag">React 前端 · S53</span>
      </div>
      <div className="pa-topbar__meta pa-muted">
        mode: <code>{APP_CONFIG.mode}</code> · session:{" "}
        <code>S{APP_CONFIG.currentSession}</code>
      </div>
    </header>
  );
}
