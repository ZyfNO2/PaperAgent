// Session 52: 侧栏 — 未来扩展点 (StepWorkbench / RAG / ThesisEval / ACP)
// 当前只展示占位, S54-S55 接入
import { APP_CONFIG } from "../../app/config";

export function SideNav() {
  return (
    <nav className="sidenav" data-testid="sidenav">
      <div className="sidenav-section">脚手架 (S52)</div>
      <a className="sidenav-item active" href="#/">
        首页
      </a>
      <a className="sidenav-item" href={APP_CONFIG.legacyWebUrl}>
        旧前端 (18182) ↗
      </a>
      <div className="sidenav-section">占位 (S53+)</div>
      <span className="sidenav-item disabled">StepWorkbench</span>
      <span className="sidenav-item disabled">Interview Mode</span>
      <span className="sidenav-item disabled">ACP 协议开关</span>
      <span className="sidenav-item disabled">RAG Eval</span>
      <span className="sidenav-item disabled">ThesisEval</span>
    </nav>
  );
}
