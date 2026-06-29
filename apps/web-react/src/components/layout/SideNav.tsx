// Session 53: SideNav — 工作台内的左侧导航
import { APP_CONFIG } from "../../app/config";

export function SideNav() {
  return (
    <nav className="pa-sidenav" data-testid="sidenav">
      <div className="pa-sidenav__section">工作台</div>
      <a className="pa-sidenav__item pa-sidenav__item--active" href="#/">
        首页 / 总览
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
        StepWorkbench
      </span>
      <span className="pa-sidenav__item pa-sidenav__item--disabled">
        Interview Mode
      </span>
      <span className="pa-sidenav__item pa-sidenav__item--disabled">
        ACP 协议开关
      </span>
      <span className="pa-sidenav__item pa-sidenav__item--disabled">
        RAG Eval
      </span>
      <span className="pa-sidenav__item pa-sidenav__item--disabled">
        ThesisEval
      </span>
    </nav>
  );
}
