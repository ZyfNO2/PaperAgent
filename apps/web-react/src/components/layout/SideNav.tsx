// Session 57: SideNav → docs rail — 工作流/证据/评估/面试/系统 分组
import { APP_CONFIG } from "../../app/config";
import { type RouteName } from "../../app/routing";

interface Props {
  currentMode?: RouteName;
}

interface NavItem {
  href: string;
  label: string;
  testId: string;
  external?: boolean;
  externalHref?: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    title: "工作流",
    items: [
      { href: "#/", label: "首页 / 总览", testId: "nav-home" },
      { href: "#/?mode=interview", label: "Interview Mode", testId: "nav-interview" },
    ],
  },
  {
    title: "评估",
    items: [
      { href: "#/?mode=rag-eval", label: "RAG Eval", testId: "nav-rag-eval" },
      { href: "#/?mode=thesis-eval", label: "ThesisEval", testId: "nav-thesis-eval" },
    ],
  },
  {
    title: "协议",
    items: [
      { href: "#/protocols", label: "协议图 / MCP/A2A/ACP", testId: "nav-protocols" },
    ],
  },
  {
    title: "系统",
    items: [
      {
        href: APP_CONFIG.legacyWebUrl,
        label: "旧前端 (18182) ↗",
        testId: "nav-legacy",
        external: true,
      },
    ],
  },
];

function itemActive(href: string, mode: RouteName): boolean {
  if (href === "#/") return mode === "home";
  if (href === "#/protocols") return mode === "protocols";
  const m = href.match(/mode=([\w-]+)/);
  if (m) return mode === m[1];
  return false;
}

export function SideNav({ currentMode }: Props) {
  const mode: RouteName = currentMode ?? "home";
  return (
    <nav className="pa-sidenav" data-testid="sidenav">
      {SECTIONS.map((sec) => (
        <div key={sec.title}>
          <div className="pa-sidenav__section">{sec.title}</div>
          {sec.items.map((it) => (
            <a
              key={it.testId}
              className={
                "pa-sidenav__item" +
                (itemActive(it.href, mode) ? " pa-sidenav__item--active" : "")
              }
              href={it.href}
              data-testid={it.testId}
              {...(it.external
                ? { target: "_blank", rel: "noreferrer" }
                : {})}
            >
              {it.label}
            </a>
          ))}
        </div>
      ))}
    </nav>
  );
}