// Session 54/55: App — 根据 hash 路由 + URL mode 切换
//  - #/                          → home
//  - #/?mode=interview           → interview
//  - #/?mode=rag-eval            → rag-eval (S55)
//  - #/?mode=thesis-eval         → thesis-eval (S55)
//  - #/protocols                 → protocols
//  - 默认                        → home
import { WorkbenchProvider } from "./features/step-workbench/WorkbenchProvider";
import { WorkbenchShell } from "./components/layout/WorkbenchShell";
import { SideNav } from "./components/layout/SideNav";
import { HomePage } from "./features/home/HomePage";
import { InterviewShell } from "./features/interview-mode/InterviewShell";
import { ThoughtPanel } from "./components/layout/ThoughtPanel";
import { RagEvalDashboard } from "./features/rag-eval/RagEvalDashboard";
import { ThesisEvalPage } from "./features/thesis-eval/ThesisEvalPage";
import { useHashRoute } from "./app/routing";

export function App() {
  const route = useHashRoute();
  const center = renderCenter(route.name);
  return (
    <WorkbenchShell
      left={<SideNav currentMode={route.name} />}
      center={
        <WorkbenchProvider key={route.name}>{center}</WorkbenchProvider>
      }
      right={<ThoughtPanel />}
    />
  );
}

function renderCenter(name: string) {
  switch (name) {
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
    case "interview":
      return <InterviewShell />;
    case "protocols":
      return <ProtocolsPage />;
    default:
      return <HomePage />;
  }
}

function ProtocolsPage() {
  return (
    <div className="pa-protocols-page" data-testid="protocols-page">
      <InterviewShell testId="protocols-via-iv" />
    </div>
  );
}
