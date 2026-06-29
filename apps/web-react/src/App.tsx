// Session 53: App — 使用 WorkbenchShell
import { WorkbenchShell } from "./components/layout/WorkbenchShell";
import { SideNav } from "./components/layout/SideNav";
import { HomePage } from "./features/home/HomePage";
import { ThoughtPanel } from "./components/layout/ThoughtPanel";

export function App() {
  return (
    <WorkbenchShell
      left={<SideNav />}
      center={<HomePage />}
      right={<ThoughtPanel />}
    />
  );
}
