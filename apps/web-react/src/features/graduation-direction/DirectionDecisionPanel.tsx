// Session 62: DirectionDecisionPanel — 普通用户查看 方向卡 + baseline + 模块
// ponytail: 复用现有 Card / Badge, 不引新组件库.

import { useState } from "react";
import { apiClient, ApiError } from "../../app/apiClient";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import type {
  BaselineRecommendation,
  DirectionDecisionReport,
  ExtensionModule,
  GraduationDirection,
} from "./directionTypes";

interface Props {
  topic?: string;
  projectId?: string | null;
  testId?: string;
}

function riskTone(level: string): "ok" | "warn" | "err" | "info" {
  if (level === "low") return "ok";
  if (level === "medium") return "info";
  return "err";
}

function effortTone(effort: string): "ok" | "warn" | "err" {
  if (effort === "S") return "ok";
  if (effort === "M") return "warn";
  return "err";
}

function reproducibilityTone(level: string): "ok" | "warn" | "err" {
  if (level === "high") return "ok";
  if (level === "medium") return "warn";
  return "err";
}

function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.body === "string") return error.body;
    if (error.body && typeof error.body === "object") {
      return JSON.stringify(error.body, null, 2);
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "未知错误";
}

function BaselineCard({ baseline }: { baseline: BaselineRecommendation }) {
  return (
    <div className="pa-gd-baseline" data-testid={`gd-baseline-${baseline.name}`}>
      <div className="pa-gd-baseline__head">
        <strong>{baseline.name}</strong>
        <Badge tone={reproducibilityTone(baseline.reproducibility)}>
          复现 {baseline.reproducibility}
        </Badge>
      </div>
      <div className="pa-gd-baseline__line">
        <span className="pa-faint">为什么选</span>
        {baseline.rationale}
      </div>
      <div className="pa-gd-baseline__line">
        <span className="pa-faint">所需数据</span>
        {baseline.required_data}
      </div>
      <div className="pa-gd-baseline__line">
        <span className="pa-faint">算力</span>
        {baseline.estimated_compute}
      </div>
      {baseline.risks.length ? (
        <ul className="pa-gd-risks">
          {baseline.risks.map((risk) => (
            <li key={risk}>{risk}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function ModuleCard({ module }: { module: ExtensionModule }) {
  return (
    <div className="pa-gd-module" data-testid={`gd-module-${module.name}`}>
      <div className="pa-gd-module__head">
        <strong>{module.name}</strong>
        <Badge tone={effortTone(module.effort)}>工作量 {module.effort}</Badge>
      </div>
      <div className="pa-gd-module__line">
        <span className="pa-faint">加在哪</span>
        {module.attach_to}
      </div>
      <div className="pa-gd-module__line">
        <span className="pa-faint">解决什么</span>
        {module.problem_solved}
      </div>
      <div className="pa-gd-module__line">
        <span className="pa-faint">消融</span>
        {module.ablation_plan}
      </div>
      {module.risks.length ? (
        <ul className="pa-gd-risks">
          {module.risks.map((risk) => (
            <li key={risk}>{risk}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function DirectionCard({
  direction,
  isRecommended,
  showScoring,
}: {
  direction: GraduationDirection;
  isRecommended: boolean;
  showScoring: boolean;
}) {
  return (
    <Card
      title={
        <span>
          {direction.title}
          {isRecommended ? (
            <Badge tone="ok" data-testid="gd-recommended-badge">
              推荐
            </Badge>
          ) : null}
        </span>
      }
      testId={`gd-direction-${direction.direction_id}`}
    >
      <div className="pa-gd-direction__head">
        <Badge tone={riskTone(direction.risk_level)}>
          风险 {direction.risk_level}
        </Badge>
        <Badge tone="info">score {direction.score.toFixed(1)}</Badge>
        <span className="pa-faint">任务: {direction.task}</span>
      </div>
      <div className="pa-gd-direction__meta">
        <div>
          <span className="pa-faint">对象</span>
          {direction.research_object}
        </div>
        <div>
          <span className="pa-faint">方法</span>
          {direction.method_route}
        </div>
      </div>
      {direction.why_graduation_friendly.length ? (
        <>
          <div className="pa-gd-section-title">为什么好毕业</div>
          <ul className="pa-gd-bullets">
            {direction.why_graduation_friendly.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}
      <div className="pa-gd-section-title">证据来源</div>
      <div className="pa-gd-evidence-summary">
        <span>
          论文 <strong>{direction.evidence_bundle.papers.length}</strong>
        </span>
        <span>
          数据集 <strong>{direction.evidence_bundle.datasets.length}</strong>
        </span>
        <span>
          工程 <strong>{direction.evidence_bundle.repos.length}</strong>
        </span>
        <span>
          RAG 片段 <strong>{direction.evidence_bundle.rag_refs.length}</strong>
        </span>
      </div>
      {direction.evidence_bundle.gaps.length ? (
        <ul className="pa-gd-gaps" data-testid={`gd-gaps-${direction.direction_id}`}>
          {direction.evidence_bundle.gaps.map((gap) => (
            <li key={gap}>{gap}</li>
          ))}
        </ul>
      ) : null}

      <div className="pa-gd-section-title">推荐 Baseline</div>
      <div className="pa-gd-baseline-list">
        {direction.recommended_baselines.map((b) => (
          <BaselineCard key={b.name} baseline={b} />
        ))}
      </div>

      <div className="pa-gd-section-title">可加模块 (消融)</div>
      <div className="pa-gd-module-list">
        {direction.extension_modules.map((m) => (
          <ModuleCard key={m.name} module={m} />
        ))}
      </div>

      {direction.fallback_route ? (
        <div className="pa-gd-fallback" data-testid={`gd-fallback-${direction.direction_id}`}>
          <span className="pa-faint">降级路径</span>
          {direction.fallback_route}
        </div>
      ) : null}

      {showScoring ? (
        <details className="pa-gd-scoring">
          <summary>评分明细 (开发者)</summary>
          <ul className="pa-gd-scoring-list">
            {direction.scoring_breakdown.map((item) => (
              <li key={item.key}>
                <strong>{item.label}</strong>: {item.score.toFixed(1)} × {item.weight.toFixed(2)} ={" "}
                {(item.score * item.weight).toFixed(1)} — {item.note}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </Card>
  );
}

export function DirectionDecisionPanel({ topic, projectId, testId }: Props) {
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<DirectionDecisionReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showScoring, setShowScoring] = useState(false);

  async function onPlan() {
    const t = (topic || "").trim();
    if (!t || loading) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await apiClient.post<DirectionDecisionReport>(
        `/api/v1/projects/${projectId ?? "ot_demo"}/graduation-direction/plan`,
        { topic: t, use_last_retrieval: true, use_local_rag: true, max_directions: 3 },
      );
      setReport(resp);
    } catch (err) {
      setError(formatError(err));
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  if (!topic || !topic.trim()) {
    return (
      <Card title="方向建议" testId={testId ?? "gd-panel"}>
        <div className="pa-faint">先在上方输入题目, 再点击"生成方向建议"</div>
      </Card>
    );
  }

  return (
    <div className="pa-gd" data-testid={testId ?? "gd-panel"}>
      <header className="pa-gd-header">
        <h3 className="pa-gd-title">方向建议 (S62 毕业友好)</h3>
        <div className="pa-gd-actions">
          <button
            type="button"
            className="pa-btn pa-btn--primary pa-btn--sm"
            onClick={onPlan}
            disabled={loading}
            data-testid="gd-plan-btn"
          >
            {loading ? "正在生成…" : "生成方向建议"}
          </button>
          <button
            type="button"
            className="pa-btn pa-btn--ghost pa-btn--sm"
            onClick={() => setShowScoring((s) => !s)}
            disabled={!report}
            data-testid="gd-toggle-scoring-btn"
          >
            {showScoring ? "隐藏评分明细" : "查看评分明细"}
          </button>
        </div>
      </header>

      {error ? (
        <Card title="生成失败" testId="gd-error">
          <div className="pa-error-card__summary">方向建议生成失败, 请稍后重试。</div>
          <pre className="pa-error-card__debug">{error}</pre>
        </Card>
      ) : null}

      {report ? (
        <>
          <div className="pa-gd-stop-note" data-testid="gd-stop-note">
            <strong>{report.stop_reason}</strong>
            {report.warnings.length ? (
              <ul>
                {report.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            ) : null}
          </div>

          <div className="pa-gd-source-counts" data-testid="gd-source-counts">
            <span>论文 {report.evidence_sources.paper ?? 0}</span>
            <span>数据集 {report.evidence_sources.dataset ?? 0}</span>
            <span>工程 {report.evidence_sources.repo ?? 0}</span>
            <span>RAG 片段 {report.evidence_sources.rag_ref ?? 0}</span>
          </div>

          <div className="pa-gd-directions">
            {report.directions.map((d) => (
              <DirectionCard
                key={d.direction_id}
                direction={d}
                isRecommended={d.direction_id === report.recommended_direction_id}
                showScoring={showScoring}
              />
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}