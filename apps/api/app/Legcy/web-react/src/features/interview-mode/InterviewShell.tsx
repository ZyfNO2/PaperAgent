// Session 54: InterviewShell — 包装 StepWorkbenchPage, 加 Interview Mode 控件
import { useState } from "react";
import { useWorkbench } from "../step-workbench/WorkbenchProvider";
import { StepWorkbenchPage } from "../step-workbench/StepWorkbenchPage";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { DemoCaseLoader } from "./DemoCaseLoader";
import { TechSwitchPanel } from "./TechSwitchPanel";
import { DeepDiveDrawer } from "./DeepDiveDrawer";
import { ProtocolMapPanel } from "../protocols/ProtocolMapPanel";
import { INTERVIEW_SCRIPTS } from "./interviewData";

interface Props {
  testId?: string;
}

export function InterviewShell({ testId }: Props) {
  const { state } = useWorkbench();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [scriptKey, setScriptKey] = useState<"3min" | "10min">("3min");
  const script = INTERVIEW_SCRIPTS[scriptKey];
  return (
    <div data-testid={testId ?? "interview-shell"}>
      <StepWorkbenchPage />
      <div className="pa-interview-stack" data-testid="iv-stack">
        <Card
          title={
            <span>
              Interview Mode{" "}
              <Badge tone="info" testId="iv-mode-badge">interview</Badge>
            </span>
          }
          testId="iv-card"
          footer={
            <div className="pa-interview-actions">
              <Button
                variant="primary"
                size="sm"
                onClick={() => setDrawerOpen(true)}
                data-testid="iv-open-deep-dive"
              >
                打开 Deep Dive
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  setScriptKey((k) => (k === "3min" ? "10min" : "3min"))
                }
                data-testid="iv-toggle-script"
              >
                切到 {scriptKey === "3min" ? "10" : "3"} 分钟脚本
              </Button>
            </div>
          }
        >
          <DemoCaseLoader testId="iv-demo-loader" />
          <div className="pa-interview-script" data-testid="iv-script">
            <div className="pa-small pa-muted">
              脚本: <strong>{scriptKey === "3min" ? "3 分钟" : "10 分钟"}</strong>
              <span className="pa-faint"> · {script.reduce((a, b) => a + b.seconds, 0)}s</span>
            </div>
            <ul className="pa-interview-script__list" data-testid="iv-script-list">
              {script.map((b, i) => (
                <li
                  key={i}
                  className="pa-interview-script__beat"
                  data-testid={`iv-script-${i}`}
                >
                  <strong>{b.label}</strong>{" "}
                  <span className="pa-faint pa-tiny">{b.seconds}s · {b.focus}</span>
                  <div className="pa-small pa-muted">{b.detail}</div>
                </li>
              ))}
            </ul>
          </div>
        </Card>
        <TechSwitchPanel testId="iv-tech-switches" />
        <ProtocolMapPanel testId="iv-protocols" />
      </div>
      <DeepDiveDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        testId="iv-deep-dive"
      />
      {state.demoLoaded ? (
        <div className="pa-faint pa-tiny" data-testid="iv-state-loaded">
          demo loaded
        </div>
      ) : null}
    </div>
  );
}
