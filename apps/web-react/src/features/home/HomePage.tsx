// Session 53: HomePage — 三栏工作台 + 中间总览
// 故意演示 "中栏 step 切换不重置左右栏": Tabs 切换不重渲染 trace/thought
import { useState } from "react";
import { useHealth } from "../health/useHealth";
import { HealthCard } from "../health/HealthCard";
import { TracePanel, type TraceEntry } from "../../components/layout/TracePanel";
import { MainStage } from "../../components/layout/MainStage";
import { Tabs } from "../../components/ui/Tabs";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Collapse } from "../../components/ui/Collapse";
import { ErrorState } from "../../components/ui/ErrorState";
import { Stepper } from "../../components/ui/Stepper";

const STEPS = [
  { key: "intake", title: "一题输入", state: "done" as const },
  { key: "keywords", title: "关键词拆解", state: "done" as const },
  { key: "retrieval", title: "三线检索", state: "active" as const },
  { key: "feasibility", title: "可行性评估", state: "pending" as const },
  { key: "report", title: "报告生成", state: "pending" as const },
];

const TRACE_ENTRIES: TraceEntry[] = [
  { id: "intake", label: "ProjectIntake", state: "done", hint: "S18" },
  { id: "topic", label: "TopicSpec", state: "done", hint: "S19" },
  { id: "plan", label: "SearchQueryPlan", state: "done", hint: "S20" },
  { id: "rag", label: "PaperRAG 检索", state: "active", hint: "S47" },
  { id: "ground", label: "Claim Grounding", state: "pending", hint: "S48" },
  { id: "thesis", label: "ThesisEval", state: "pending", hint: "S51" },
];

export function HomePage() {
  const health = useHealth();
  const [counter, setCounter] = useState(0);

  return (
    <>
      <TracePanel entries={TRACE_ENTRIES} testId="trace-panel" />
      <MainStage
        title="PaperAgent · 工作台总览"
        stepper={STEPS}
        testId="main-stage"
      >
        <Tabs
          testId="overview-tabs"
          items={[
            {
              key: "summary",
              label: "总览",
              content: (
                <div className="overview-grid" data-testid="overview-summary">
                  <Card title="健康" testId="card-health">
                    <HealthCard state={health} />
                  </Card>
                  <Card
                    title="迁移阶段"
                    testId="card-phase"
                    footer={
                      <span>
                        新前端 <code>apps/web-react</code> (18183) 与旧{" "}
                        <code>apps/web</code> (18182) 并行
                      </span>
                    }
                  >
                    <Stepper
                      items={[
                        { key: "s52", title: "S52 脚手架", state: "done" },
                        { key: "s53", title: "S53 设计系统", state: "done" },
                        { key: "s54", title: "S54 StepWorkbench", state: "done" },
                        { key: "s55", title: "S55 RAG 接入", state: "active" },
                        { key: "s56", title: "S56 切换收口", state: "pending" },
                      ]}
                      testId="phase-stepper"
                    />
                  </Card>
                  <Card title="S50 · RAG 评估" testId="card-s50">
                    <div className="pa-small pa-muted">
                      7 指标 (recall@5/MRR/NDCG/citation_precision/
                      evidence_coverage/unsupported_claim_rate/faithfulness)
                      + 回归基线。
                    </div>
                    <Badge tone="ok">baseline 0.68 / 0.76 / 1.0</Badge>
                    <div className="pa-interview-actions">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => (window.location.hash = "#/?mode=rag-eval")}
                        data-testid="home-go-rag-eval"
                      >
                        打开 RAG Eval
                      </Button>
                    </div>
                  </Card>
                  <Card title="S51 · ThesisEval" testId="card-s51">
                    <div className="pa-small pa-muted">
                      100 篇工科学位论文测试集, 4 任务评估闭环, 三态降级。
                    </div>
                    <Badge tone="info">100 papers · 4 tasks</Badge>
                    <div className="pa-interview-actions">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() =>
                          (window.location.hash = "#/?mode=thesis-eval")
                        }
                        data-testid="home-go-thesis-eval"
                      >
                        打开 ThesisEval
                      </Button>
                    </div>
                  </Card>
                </div>
              ),
            },
            {
              key: "demo",
              label: "组件演示",
              content: (
                <div
                  className="overview-grid"
                  data-testid="overview-demo"
                >
                  <Card title="Button 演示" testId="card-button">
                    <div className="button-row">
                      <Button variant="primary" data-testid="btn-primary">
                        Primary
                      </Button>
                      <Button
                        variant="secondary"
                        loading
                        data-testid="btn-loading"
                      >
                        Loading
                      </Button>
                      <Button variant="ghost" data-testid="btn-ghost">
                        Ghost
                      </Button>
                      <Button
                        variant="secondary"
                        disabled
                        data-testid="btn-disabled"
                      >
                        Disabled
                      </Button>
                      <Button
                        variant="danger"
                        data-testid="btn-danger"
                        onClick={() => alert("danger")}
                      >
                        Danger
                      </Button>
                    </div>
                    <div className="pa-small pa-muted">
                      点击次数: <code data-testid="btn-counter">{counter}</code>{" "}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setCounter(counter + 1)}
                        data-testid="btn-incr"
                      >
                        +1
                      </Button>
                    </div>
                  </Card>
                  <Card title="Badge / Collapse" testId="card-badge">
                    <div className="badge-row">
                      <Badge tone="ok">ok</Badge>
                      <Badge tone="warn">warn</Badge>
                      <Badge tone="err">err</Badge>
                      <Badge tone="info">info</Badge>
                      <Badge tone="neutral">neutral</Badge>
                    </div>
                    <Collapse title="可折叠区域 (默认折叠)" testId="collapse-default">
                      <div className="pa-small pa-muted">
                        高级配置: 双卡/单卡/批大小/学习率...
                      </div>
                    </Collapse>
                  </Card>
                  <Card title="ErrorState 演示" testId="card-error">
                    <ErrorState
                      title="后端不可达"
                      message="uvicorn 未起或端口 18181 被占用"
                      onRetry={() => alert("retry")}
                      testId="err-demo"
                    />
                  </Card>
                </div>
              ),
            },
          ]}
        />
      </MainStage>
      <></>
    </>
  );
}
