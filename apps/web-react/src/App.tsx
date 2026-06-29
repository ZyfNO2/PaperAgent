// Session 54: App — 根据 hash 路由 + URL mode 切换
//  - #/ 或 #/?mode=interview → interview
//  - #/protocols → protocols
//  - 默认 → home
import { WorkbenchProvider } from "./features/step-workbench/WorkbenchProvider";
import { WorkbenchShell } from "./components/layout/WorkbenchShell";
import { SideNav } from "./components/layout/SideNav";
import { HomePage } from "./features/home/HomePage";
import { InterviewShell } from "./features/interview-mode/InterviewShell";
import { ThoughtPanel } from "./components/layout/ThoughtPanel";
import { useHashRoute } from "./app/routing";

export function App() {
  const route = useHashRoute();
  const center =
    route.name === "interview" ? (
      <InterviewShell />
    ) : route.name === "protocols" ? (
      <ProtocolsPage />
    ) : (
      <HomePage />
    );
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

function ProtocolsPage() {
  return (
    <div className="pa-protocols-page" data-testid="protocols-page">
      <InterviewShell testId="protocols-via-iv" />
    </div>
  );
}
