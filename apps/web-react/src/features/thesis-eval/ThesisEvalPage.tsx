// Session 55: ThesisEval 页面 — 单题评估 + 子集 run + baseline + 证据链
// ponytail: 1 page 5 section inline, 不拆 5 个文件, state 用 useState 局部
import { useEffect, useState } from "react";
import { apiClient, ApiError } from "../../app/apiClient";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import type {
  ThesisAssessment,
  ThesisEvalBaselineResponse,
  ThesisEvalReport,
  SubsetName,
  VerifiedStatus,
} from "./thesisEvalTypes";

const SUBSETS: { key: SubsetName; label: string; description: string }[] = [
  { key: "smoke_20", label: "smoke_20", description: "20 题快速冒烟" },
  { key: "regression_60", label: "regression_60", description: "60 题回归基线" },
  { key: "hard_20", label: "hard_20", description: "20 题困难子集" },
  { key: "all_100", label: "all_100", description: "100 题全集" },
];

const VERIFIED_TONE: Record<VerifiedStatus, "ok" | "warn" | "err"> = {
  verified: "ok",
  partial: "warn",
  failed: "err",
};

const VERIFIED_LABEL: Record<VerifiedStatus, string> = {
  verified: "verified · 题录完整",
  partial: "partial · 仅部分字段",
  failed: "failed · 抓取失败, 已降级",
};

function ThesisAssessForm({
  onAssess,
  loading,
}: {
  onAssess: (id: string) => Promise<void>;
  loading: boolean;
}) {
  const [thesisId, setThesisId] = useState("ENG-THESIS-001");
  return (
    <Card title="单题评估" testId="thesis-assess-card">
      <div className="pa-form-row">
        <label className="pa-small pa-muted">thesis_id</label>
        <input
          className="pa-input"
          value={thesisId}
          onChange={(e) => setThesisId(e.target.value)}
          data-testid="thesis-id-input"
        />
      </div>
      <div className="pa-interview-actions">
        <Button
          variant="primary"
          size="sm"
          disabled={loading || !thesisId}
          onClick={() => onAssess(thesisId)}
          data-testid="thesis-assess-btn"
        >
          {loading ? "评估中…" : "评估"}
        </Button>
      </div>
    </Card>
  );
}

function ThesisAssessmentResult({
  assessment,
}: {
  assessment: ThesisAssessment;
}) {
  const r = assessment.record;
  return (
    <Card title={`评估结果 · ${assessment.thesis_id}`} testId="thesis-result-card">
      <div className="pa-thesis-meta">
        <Badge tone={VERIFIED_TONE[r.verified_status]} testId="thesis-verified-badge">
          {VERIFIED_LABEL[r.verified_status]}
        </Badge>
        <span className="pa-faint pa-tiny" data-testid="thesis-source-url">
          <a href={r.source_url} target="_blank" rel="noreferrer">
            source_url
          </a>
        </span>
      </div>
      <div className="pa-small pa-muted">{r.title}</div>
      <table className="pa-table pa-tiny">
        <tbody>
          <tr>
            <th>difficulty</th>
            <td data-testid="thesis-difficulty">{assessment.difficulty ?? "—"}</td>
          </tr>
          <tr>
            <th>cycle</th>
            <td data-testid="thesis-cycle">{assessment.cycle ?? "—"}</td>
          </tr>
          <tr>
            <th>repeatability</th>
            <td>{assessment.repeatability ?? "—"}</td>
          </tr>
          <tr>
            <th>feasibility</th>
            <td data-testid="thesis-feasibility">
              {assessment.graduation_feasibility ?? "—"}
            </td>
          </tr>
          <tr>
            <th>reality_tier</th>
            <td>{assessment.reality_tier ?? "—"}</td>
          </tr>
          <tr>
            <th>confidence</th>
            <td>{assessment.confidence.toFixed(2)}</td>
          </tr>
        </tbody>
      </table>
      <div className="pa-thesis-tags" data-testid="thesis-tags">
        {assessment.experiment_needs.map((tag) => (
          <Badge key={tag} tone="info" testId={`thesis-tag-${tag}`}>
            {tag}
          </Badge>
        ))}
      </div>
      {assessment.unsupported_claims.length > 0 ? (
        <div className="pa-thesis-warn" data-testid="thesis-unsupported">
          <Badge tone="warn">unsupported</Badge>{" "}
          {assessment.unsupported_claims.join("; ")}
        </div>
      ) : null}
    </Card>
  );
}

function ThesisEvidenceTrace({ assessment }: { assessment: ThesisAssessment | null }) {
  if (!assessment) return null;
  return (
    <Card title="Evidence Trace" testId="thesis-trace-card">
      <ul className="pa-trace" data-testid="thesis-trace-list">
        {assessment.evidence_refs.map((ref, i) => (
          <li key={i} data-testid={`thesis-trace-${i}`}>
            <Badge tone="info">ref</Badge>{" "}
            <span className="pa-small">
              {ref.source ?? "unknown"} {ref.ref_id ?? ""} {ref.url ?? ""}
            </span>
            {ref.snippet ? (
              <div className="pa-faint pa-tiny">{ref.snippet}</div>
            ) : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function ThesisBaselinePanel({
  baseline,
  onRefresh,
  loading,
}: {
  baseline: ThesisEvalBaselineResponse | null;
  onRefresh: () => void;
  loading: boolean;
}) {
  return (
    <Card
      title="Baseline"
      testId="thesis-baseline-card"
      footer={
        <Button
          variant="secondary"
          size="sm"
          onClick={onRefresh}
          data-testid="thesis-baseline-refresh"
        >
          刷新
        </Button>
      }
    >
      {loading ? (
        <div className="pa-faint">加载中…</div>
      ) : baseline?.baseline ? (
        <div data-testid="thesis-baseline-summary">
          <div className="pa-small pa-muted">
            subset: <strong>{baseline.baseline.subset}</strong> · count:{" "}
            {baseline.baseline.thesis_count}
          </div>
          <div className="pa-small pa-muted">
            url_fidelity:{" "}
            {(baseline.baseline.aggregate_metrics.url_fidelity ?? 0).toFixed(3)}{" "}
            · year_accuracy:{" "}
            {(baseline.baseline.aggregate_metrics.year_accuracy ?? 0).toFixed(3)}
          </div>
        </div>
      ) : (
        <div className="pa-faint" data-testid="thesis-baseline-empty">
          {baseline?.message ?? "暂无 baseline"}
        </div>
      )}
    </Card>
  );
}

function ThesisEvalRunPanel({
  subset,
  onSubset,
  onRun,
  running,
}: {
  subset: SubsetName;
  onSubset: (k: SubsetName) => void;
  onRun: () => void;
  running: boolean;
}) {
  return (
    <Card title="测试集评估" testId="thesis-run-card">
      <div className="pa-subset-grid" data-testid="thesis-subset-grid">
        {SUBSETS.map((s) => (
          <button
            key={s.key}
            className={
              "pa-subset-btn" +
              (s.key === subset ? " pa-subset-btn--active" : "")
            }
            onClick={() => onSubset(s.key)}
            data-testid={`thesis-subset-${s.key}`}
            data-active={s.key === subset ? "yes" : "no"}
          >
            <strong>{s.label}</strong>
            <span className="pa-faint pa-tiny">{s.description}</span>
          </button>
        ))}
      </div>
      <div className="pa-interview-actions">
        <Button
          variant="primary"
          size="sm"
          disabled={running}
          onClick={onRun}
          data-testid="thesis-run-btn"
        >
          {running ? "运行中…" : `跑 ${subset}`}
        </Button>
      </div>
    </Card>
  );
}

export function ThesisEvalPage({ testId }: { testId?: string }) {
  const [assessment, setAssessment] = useState<ThesisAssessment | null>(null);
  const [subset, setSubset] = useState<SubsetName>("smoke_20");
  const [report, setReport] = useState<ThesisEvalReport | null>(null);
  const [baseline, setBaseline] = useState<ThesisEvalBaselineResponse | null>(
    null,
  );
  const [loadingAssess, setLoadingAssess] = useState(false);
  const [loadingRun, setLoadingRun] = useState(false);
  const [loadingBaseline, setLoadingBaseline] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshBaseline = async () => {
    setLoadingBaseline(true);
    try {
      const data = await apiClient.get<ThesisEvalBaselineResponse>(
        "/api/v1/thesis-eval/eval/baseline",
      );
      setBaseline(data);
    } catch (e) {
      setBaseline(null);
    } finally {
      setLoadingBaseline(false);
    }
  };

  useEffect(() => {
    refreshBaseline();
  }, []);

  const onAssess = async (thesisId: string) => {
    setLoadingAssess(true);
    setError(null);
    try {
      const data = await apiClient.post<ThesisAssessment>(
        "/api/v1/thesis-eval/assess",
        { thesis_id: thesisId },
      );
      setAssessment(data);
    } catch (e) {
      if (e instanceof ApiError) setError(`${e.status} ${e.message}`);
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingAssess(false);
    }
  };

  const onRun = async () => {
    setLoadingRun(true);
    setError(null);
    try {
      const data = await apiClient.post<ThesisEvalReport>(
        "/api/v1/thesis-eval/eval/run",
        { subset, use_llm: false, save_baseline: false },
      );
      setReport(data);
    } catch (e) {
      if (e instanceof ApiError) setError(`${e.status} ${e.message}`);
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingRun(false);
    }
  };

  return (
    <div className="pa-thesis-eval" data-testid={testId ?? "thesis-eval-page"}>
      <Card title="ThesisEval" testId="thesis-eval-card">
        <div className="pa-small pa-muted">
          工科学位论文题录可行性评估 — 9 标签 · 4 档难度 · verified / partial / failed 三态降级
        </div>
        {error ? (
          <div className="pa-error pa-tiny" data-testid="thesis-error">
            {error}
          </div>
        ) : null}
      </Card>
      <ThesisAssessForm onAssess={onAssess} loading={loadingAssess} />
      {assessment ? <ThesisAssessmentResult assessment={assessment} /> : null}
      <ThesisEvidenceTrace assessment={assessment} />
      <ThesisEvalRunPanel
        subset={subset}
        onSubset={setSubset}
        onRun={onRun}
        running={loadingRun}
      />
      {report ? (
        <Card title={`Report · ${report.subset}`} testId="thesis-report-card">
          <div className="pa-small pa-muted" data-testid="thesis-report-summary">
            count: {report.thesis_count} · run_id: {report.run_id}
          </div>
          <table className="pa-table pa-tiny" data-testid="thesis-report-table">
            <thead>
              <tr>
                <th>任务指标</th>
                <th>值</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(report.aggregate_metrics).map(([k, v]) => (
                <tr key={k} data-testid={`thesis-metric-${k}`}>
                  <td>{k}</td>
                  <td>{typeof v === "number" ? v.toFixed(3) : String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {report.regressions.length > 0 ? (
            <div data-testid="thesis-regressions">
              <Badge tone="err">regress</Badge>{" "}
              {report.regressions.join("; ")}
            </div>
          ) : null}
        </Card>
      ) : null}
      <ThesisBaselinePanel
        baseline={baseline}
        onRefresh={refreshBaseline}
        loading={loadingBaseline}
      />
    </div>
  );
}