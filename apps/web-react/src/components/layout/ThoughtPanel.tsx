// Session 53: ThoughtPanel — 右侧 LLM 思维 / 对话 / Skill 调用占位
import { Badge } from "../ui/Badge";
import { Collapse } from "../ui/Collapse";
import { Tabs } from "../ui/Tabs";

export interface ThoughtPanelProps {
  testId?: string;
}

export function ThoughtPanel({ testId }: ThoughtPanelProps) {
  return (
    <aside
      className="pa-thought-panel"
      data-testid={testId ?? "thought-panel"}
      aria-label="LLM 思维/对话"
    >
      <Tabs
        testId="thought-tabs"
        items={[
          {
            key: "thought",
            label: "LLM 思维",
            content: (
              <div className="pa-thought-panel__block" data-testid="thought-stream">
                <div className="pa-muted pa-small">
                  流式思维区。S53 占位, S55 接入真实 LLM 输出。
                </div>
                <pre className="pa-thought-panel__demo pa-mono pa-tiny">
                  {`[planner] parse: 一题 → 拆解\n[retriever] query: 关键词 x3\n[reality] tier: existing_env`}
                </pre>
              </div>
            ),
          },
          {
            key: "chat",
            label: "对话",
            content: (
              <div className="pa-thought-panel__block" data-testid="chat-stream">
                <div className="pa-muted pa-small">
                  对话区, S54+ 接入 (Interview Mode / Tech Switches)。
                </div>
              </div>
            ),
          },
          {
            key: "skills",
            label: "Skill",
            content: (
              <div className="pa-thought-panel__block" data-testid="skill-stream">
                <Collapse title="claim_grounding" defaultOpen={true} testId="skill-claim-grounding">
                  <div className="pa-small pa-muted">
                    引用检查, evidence_refs 强制 (S48)
                  </div>
                </Collapse>
                <Collapse title="feasibility_card" defaultOpen={false} testId="skill-feasibility">
                  <div className="pa-small pa-muted">资源四层 (S45)</div>
                </Collapse>
                <Collapse title="small_paper_extractor" defaultOpen={false} testId="skill-small-paper">
                  <div className="pa-small pa-muted">Track B 扩展 (S49)</div>
                </Collapse>
                <div className="pa-thought-panel__hint">
                  <Badge tone="info" testId="skill-count">5</Badge>{" "}
                  <span className="pa-muted pa-tiny">5 skill 注册 (S45/S48/S49/S51/...)</span>
                </div>
              </div>
            ),
          },
        ]}
      />
    </aside>
  );
}
