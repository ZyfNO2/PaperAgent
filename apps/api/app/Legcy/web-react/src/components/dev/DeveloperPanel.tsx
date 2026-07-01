// Session 59: DeveloperPanel — 右侧抽屉, 收纳 RAG/ThesisEval/Interview/Protocols/
// Health/旧前端/Playwright + ThoughtPanel TUI console. 仅 dev-mode 可见.
// ponytail: 状态来源 = localStorage + paperagent:dev-mode 事件; 用 useState 镜像.
import { useEffect, useState } from "react";
import { navigate } from "../../app/routing";
import { DEV_MODE_STORAGE_KEY } from "../layout/TopBar";
import { ThoughtPanel } from "../layout/ThoughtPanel";

const STORAGE_KEY = DEV_MODE_STORAGE_KEY;

interface DevNavItem {
  label: string;
  href: string;
  testId: string;
  external?: boolean;
}

interface DevNavSection {
  title: string;
  items: DevNavItem[];
}

function readDevOpen(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(STORAGE_KEY) === "1";
}

const NAV_GROUPS: DevNavSection[] = [
  {
    title: "评估",
    items: [
      { label: "RAG Eval", href: "#/?mode=rag-eval", testId: "dev-nav-rag-eval" },
      { label: "ThesisEval", href: "#/?mode=thesis-eval", testId: "dev-nav-thesis-eval" },
    ],
  },
  {
    title: "检索",
    items: [
      { label: "Retrieval Debug", href: "#/?mode=retrieval-debug", testId: "dev-nav-retrieval-debug" },
    ],
  },
  {
    title: "面试 / 演示",
    items: [
      { label: "Interview Mode", href: "#/?mode=interview", testId: "dev-nav-interview" },
      { label: "Protocol Map", href: "#/protocols", testId: "dev-nav-protocols" },
    ],
  },
  {
    title: "系统",
    items: [
      { label: "健康检查 /health", href: "http://127.0.0.1:18183/health", external: true, testId: "dev-nav-health" },
      { label: "旧前端 (18182)", href: "http://127.0.0.1:18182", external: true, testId: "dev-nav-legacy" },
    ],
  },
];

export function DeveloperPanel() {
  const [open, setOpen] = useState<boolean>(() => readDevOpen());

  useEffect(() => {
    const onChange = () => setOpen(readDevOpen());
    window.addEventListener("paperagent:dev-mode", onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener("paperagent:dev-mode", onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const onKey = (e: KeyboardEvent) => {
      // Ctrl + `  (backtick)
      if (e.ctrlKey && (e.key === "`" || e.code === "Backquote")) {
        e.preventDefault();
        const next = !readDevOpen();
        window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
        window.dispatchEvent(new CustomEvent("paperagent:dev-mode", { detail: next }));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!open) return null;

  return (
    <>
      <div
        className="pa-dev-scrim"
        data-testid="dev-scrim"
        onClick={() => {
          window.localStorage.setItem(STORAGE_KEY, "0");
          window.dispatchEvent(new CustomEvent("paperagent:dev-mode", { detail: false }));
        }}
      />
      <aside
        className="pa-dev-panel"
        role="dialog"
        aria-label="开发者窗口"
        data-testid="developer-panel"
      >
        <header className="pa-dev-panel__header">
          <div>
            <h2 className="pa-dev-panel__title">开发者窗口</h2>
            <p className="pa-dev-panel__hint">
              这些内容用于开发、验收和面试展示，默认不出现在普通用户流程中。
            </p>
          </div>
          <button
            type="button"
            className="pa-dev-panel__close"
            onClick={() => {
              window.localStorage.setItem(STORAGE_KEY, "0");
              window.dispatchEvent(new CustomEvent("paperagent:dev-mode", { detail: false }));
            }}
            data-testid="dev-close"
            aria-label="关闭开发者窗口"
          >
            ×
          </button>
        </header>
        <nav className="pa-dev-panel__nav" data-testid="dev-nav">
          {NAV_GROUPS.map((sec) => (
            <div key={sec.title}>
              <div className="pa-dev-panel__section">{sec.title}</div>
              {sec.items.map((it) => (
                <a
                  key={it.testId}
                  className="pa-dev-panel__item"
                  href={it.href}
                  data-testid={it.testId}
                  {...(it.external
                    ? { target: "_blank", rel: "noreferrer" }
                    : {
                        onClick: (e: React.MouseEvent) => {
                          e.preventDefault();
                          navigate(it.href.slice(1)); // strip leading #
                        },
                      })}
                >
                  {it.label}
                </a>
              ))}
            </div>
          ))}
          <div>
            <div className="pa-dev-panel__section">调试 / 面试 / 测试</div>
            <p className="pa-dev-panel__note">
              TUI agent console + raw trace 已展开在下方。
              Ctrl + ` 切换本窗口。
            </p>
          </div>
        </nav>
        <div className="pa-dev-panel__console" data-testid="dev-console-slot">
          <ThoughtPanel testId="dev-thought-panel" />
        </div>
      </aside>
    </>
  );
}
