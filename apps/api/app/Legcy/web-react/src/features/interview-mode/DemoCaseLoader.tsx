// Session 54: DemoCaseLoader — 加载 Interview 模式固定 demo case
import { useWorkbench } from "../step-workbench/WorkbenchProvider";
import {
  DEMO_CASE_TOPIC,
  DEMO_CASE_DISCLAIMER,
  DEMO_CASE_INTRO,
} from "./interviewData";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";

interface Props {
  testId?: string;
}

export function DemoCaseLoader({ testId }: Props) {
  const { state, dispatch } = useWorkbench();
  if (state.demoLoaded) {
    return (
      <Card title="Demo Case 已加载" testId={testId ?? "demo-case-loaded"}>
        <div className="pa-small">
          <strong>题目:</strong> {state.demoTopic}
        </div>
        <div className="pa-small pa-muted">{state.demoDisclaimer}</div>
      </Card>
    );
  }
  return (
    <Card
      title="加载 Demo Case"
      testId={testId ?? "demo-case-loader"}
      footer={
        <Button
          variant="primary"
          onClick={() => {
            dispatch({ type: "LOAD_DEMO_CASE", topic: DEMO_CASE_TOPIC, disclaimer: DEMO_CASE_DISCLAIMER });
            dispatch({ type: "APPEND_LLM", kind: "assistant_reply", text: DEMO_CASE_INTRO, step: null });
            dispatch({ type: "APPEND_TRACE", kind: "demo_case", text: "Interview Mode 已切换到固定 Demo Case", step: null });
          }}
          data-testid="demo-load"
        >
          加载演示案例
        </Button>
      }
    >
      <div className="pa-small pa-muted">
        固定 <code>{DEMO_CASE_TOPIC}</code>, 便于 3 分钟 / 10 分钟脚本稳定复现。
      </div>
    </Card>
  );
}
