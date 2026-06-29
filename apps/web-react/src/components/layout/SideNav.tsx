// Session 53/54/55: SideNav — 工作台内的左侧导航
import { APP_CONFIG } from "../../app/config";
import { navigate, type RouteName } from "../../app/routing";

interface Props {
  currentMode?: RouteName;
}

export function SideNav({ currentMode }: Props) {
  const mode = currentMode ?? "home";
  const isHome = mode === "home";
  const isInterview = mode === "interview";
  const isProtocols = mode === "protocols";
  const isRagEval = mode === "rag-eval";
  const isThesisEval = mode === "thesis-eval";
  return (
    <nav className="pa-sidenav" data-testid="sidenav">
      <div className="pa-sidenav__section">工作台</div>
      <a
        className={
          "pa-sidenav__item" + (isHome ? " pa-sidenav__item--active" : "")
        }
        href="#/"
        data-testid="nav-home"
      >
        首页 / 总览
      </a>
      <a
        className={
          "pa-sidenav__item" +
          (isInterview ? " pa-sidenav__item--active" : "")
        }
        href="#/?mode=interview"
        data-testid="nav-interview"
      >
        Interview Mode
      </a>
      <a
        className={
          "pa-sidenav__item" +
          (isRagEval ? " pa-sidenav__item--active" : "")
        }
        href="#/?mode=rag-eval"
        data-testid="nav-rag-eval"
      >
        RAG Eval
      </a>
      <a
        className={
          "pa-sidenav__item" +
          (isThesisEval ? " pa-sidenav__item--active" : "")
        }
        href="#/?mode=thesis-eval"
        data-testid="nav-thesis-eval"
      >
        ThesisEval
      </a>
      <a
        className={
          "pa-sidenav__item" +
          (isProtocols ? " pa-sidenav__item--active" : "")
        }
        href="#/protocols"
        data-testid="nav-protocols"
      >
        协议图
      </a>
      <a
        className="pa-sidenav__item"
        href={APP_CONFIG.legacyWebUrl}
        target="_blank"
        rel="noreferrer"
      >
        旧前端 (18182) ↗
      </a>
      <div className="pa-sidenav__section">规划中</div>
      <span className="pa-sidenav__item pa-sidenav__item--disabled">
        StepWorkbench 1.0
      </span>
      <span className="pa-sidenav__item pa-sidenav__item--disabled">
        Paper Library
      </span>
    </nav>
  );
}

export { navigate };
