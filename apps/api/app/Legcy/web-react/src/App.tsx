// Session 59: App — 普通模式用 UserShell (极简主工作台), 开发者模式用 WorkbenchShell.
// 路由:
//  - #/                          → home (= workbench, UserWorkbenchPage)
//  - #/workbench                 → workbench (UserWorkbenchPage)
//  - #/?mode=interview           → interview (WorkbenchShell)
//  - #/?mode=rag-eval            → rag-eval (WorkbenchShell)
//  - #/?mode=thesis-eval         → thesis-eval (WorkbenchShell)
//  - #/protocols                 → protocols (WorkbenchShell)
// 普通首屏不再需要点 "进入工作台"; 高级内容 (RAG Eval / ThesisEval / Interview / Protocol Map / Trace console)
// 全部迁入 DeveloperPanel 抽屉 (Ctrl + ` 触发).
import { WorkbenchProvider } from "./features/step-workbench/WorkbenchProvider";
import { WorkbenchShell } from "./components/layout/WorkbenchShell";
import { SideNav } from "./components/layout/SideNav";
import { ThoughtPanel } from "./components/layout/ThoughtPanel";
import { UserShell } from "./components/layout/UserShell";
import { UserWorkbenchPage } from "./features/user-workbench/UserWorkbenchPage";
import { HomePage } from "./features/home/HomePage";
import { InterviewShell } from "./features/interview-mode/InterviewShell";
import { RagEvalDashboard } from "./features/rag-eval/RagEvalDashboard";
import { ThesisEvalPage } from "./features/thesis-eval/ThesisEvalPage";
import { useHashRoute } from "./app/routing";
import { StepWorkbenchPage } from "./features/step-workbench/StepWorkbenchPage";

export function App() {
  const route = useHashRoute();
  const isUserMode = route.name === "home" || route.name === "workbench";

  if (isUserMode) {
    return (
      <WorkbenchProvider>
        <UserShell>
          <UserWorkbenchPage />
        </UserShell>
      </WorkbenchProvider>
    );
  }

  const center = renderCenter(route.name);
  return (
    <WorkbenchProvider>
      <WorkbenchShell
        left={<SideNav currentMode={route.name} />}
        center={center}
        right={<ThoughtPanel />}
      />
    </WorkbenchProvider>
  );
}

function renderCenter(name: string) {
  switch (name) {
    case "interview":
      return <InterviewShell />;
    case "rag-eval":
      return (
        <div className="pa-route-page" data-testid="rag-eval-page">
          <RagEvalDashboard testId="rag-eval-route" />
        </div>
      );
    case "thesis-eval":
      return (
        <div className="pa-route-page" data-testid="thesis-eval-route">
          <ThesisEvalPage />
        </div>
      );
    case "protocols":
      return <ProtocolsPage />;
    default:
      // StepWorkbenchPage 仍保留以兼容 #/workbench?mode=... 的旧 URL
      return <StepWorkbenchPage testId="step-workbench-page" />;
  }
}

function ProtocolsPage() {
  return (
    <div className="pa-protocols-page" data-testid="protocols-page">
      <InterviewShell testId="protocols-via-iv" />
    </div>
  );
}