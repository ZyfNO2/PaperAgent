// Session 52: App 入口 — 路由 + 布局
import { Shell } from "./components/layout/Shell";
import { SideNav } from "./components/layout/SideNav";
import { TopBar } from "./components/layout/TopBar";
import { HomePage } from "./features/home/HomePage";
import { useRoute } from "./app/routes";

export function App() {
  const [route] = useRoute();

  return (
    <div className="app-root">
      <TopBar />
      <Shell
        left={<SideNav />}
        center={route === "home" ? <HomePage /> : <HomePage />}
        right={
          <aside className="right-pane" data-testid="right-pane">
            <div className="muted small">
              右侧: 未来 LLM 思维/对话/Trace 区
              <br />
              S53-S55 接入
            </div>
          </aside>
        }
      />
    </div>
  );
}
