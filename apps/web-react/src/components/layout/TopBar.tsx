// Session 57: TopBar OpenCode 化 — wordmark 左 + 导航右 + 黑色主按钮
import { navigate, useHashRoute } from "../../app/routing";

const NAV_ITEMS: Array<{ mode: string; label: string }> = [
  { mode: "", label: "工作台" },
  { mode: "rag-eval", label: "RAG" },
  { mode: "thesis-eval", label: "ThesisEval" },
  { mode: "interview", label: "面试" },
  { mode: "protocols", label: "协议" },
];

function href(mode: string): string {
  if (!mode) return "#/";
  if (mode === "protocols") return "#/protocols";
  return `#/?mode=${mode}`;
}

export function TopBar() {
  const { name } = useHashRoute();
  const currentMode = name === "protocols" ? "protocols" : name;
  return (
    <header className="pa-topbar" data-testid="topbar">
      <div className="pa-topbar__brand">
        <span className="pa-topbar__mark" aria-hidden>pa</span>
        <span className="pa-topbar__name">paperagent</span>
        <span className="pa-topbar__tag">S57 · docs</span>
      </div>
      <nav className="pa-topbar__nav" aria-label="primary" data-testid="topnav">
        {NAV_ITEMS.map((it) => {
          const active = currentMode === it.mode;
          return (
            <a
              key={it.label}
              href={href(it.mode)}
              className={
                "pa-topbar__nav-item" +
                (active ? " pa-topbar__nav-item--active" : "")
              }
              data-testid={`topnav-${it.mode || "home"}`}
            >
              {it.label}
            </a>
          );
        })}
      </nav>
      <div className="pa-topbar__actions">
        <a
          href="#/?mode=interview&demo=case1"
          className="pa-topbar__cta"
          onClick={(e) => {
            e.preventDefault();
            navigate("/?mode=interview&demo=case1");
          }}
          data-testid="topbar-demo"
        >
          加载 Demo
        </a>
        <a
          className="pa-topbar__legacy"
          href="http://127.0.0.1:18182"
          target="_blank"
          rel="noreferrer"
          data-testid="topbar-legacy"
        >
          旧前端 ↗
        </a>
      </div>
    </header>
  );
}