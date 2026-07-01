// Session 55: RAG Eval Dashboard — 3 panel: baseline + metrics + regression
// ponytail: 1 page, 3 组件 — 不做 store / context / facade, useState 局部足够
import { useEffect, useState } from "react";
import { apiClient, ApiError } from "../../app/apiClient";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import type {
  RagEvalBaselineResponse,
  RagEvalRunRequest,
  RagEvalRunResponse,
  RagEvalSeedLibraryResponse,
  RagEvalReport,
} from "./ragEvalTypes";

const PROJECT_ID = "paperagent-demo"; // ponytail: demo 默认, S56 换成真实 project

interface MetricRow {
  key: string;
  label: string;
  value: number;
  unit: string;
  /** 越大越好 (recall) vs 越小越好 (latency) */
  direction: "up" | "down";
  baseline?: number;
}

function buildMetricRows(
  report: Partial<Pick<RagEvalReport, "aggregate_retrieval" | "aggregate_answer" | "aggregate_system">>,
): MetricRow[] {
  const r = report.aggregate_retrieval ?? { recall_at_5: 0, mrr: 0, ndcg_at_5: 0, hit_rate: 0 };
  const a = report.aggregate_answer ?? { citation_precision: 0, evidence_coverage: 0, unsupported_claim_rate: 0, faithfulness: 0 };
  const s = report.aggregate_system ?? { latency_p50_ms: 0, latency_p95_ms: 0, total_questions: 0, fallback_rate: 0 };
  return [
    { key: "recall_at_5", label: "Recall@5", value: r.recall_at_5, unit: "", direction: "up" },
    { key: "mrr", label: "MRR", value: r.mrr, unit: "", direction: "up" },
    { key: "ndcg_at_5", label: "NDCG@5", value: r.ndcg_at_5, unit: "", direction: "up" },
    { key: "hit_rate", label: "Hit Rate", value: r.hit_rate, unit: "", direction: "up" },
    { key: "citation_precision", label: "Citation Precision", value: a.citation_precision, unit: "", direction: "up" },
    { key: "evidence_coverage", label: "Evidence Coverage", value: a.evidence_coverage, unit: "", direction: "up" },
    { key: "unsupported_claim_rate", label: "Unsupported Claim", value: a.unsupported_claim_rate, unit: "", direction: "down" },
    { key: "faithfulness", label: "Faithfulness", value: a.faithfulness, unit: "", direction: "up" },
    { key: "latency_p50", label: "Latency p50", value: s.latency_p50_ms, unit: "ms", direction: "down" },
    { key: "latency_p95", label: "Latency p95", value: s.latency_p95_ms, unit: "ms", direction: "down" },
    { key: "fallback_rate", label: "Fallback Rate", value: s.fallback_rate, unit: "", direction: "down" },
  ];
}

function fmt(value: number, unit: string): string {
  if (unit === "ms") return value.toFixed(0);
  return value.toFixed(3);
}

function isRegression(
  row: MetricRow,
  current: number,
  baseline?: number,
): boolean {
  if (baseline === undefined) return false;
  const delta = current - baseline;
  return row.direction === "down" ? delta > 0.05 : delta < -0.05;
}

interface RagMetricTableProps {
  rows: MetricRow[];
  baseline?: RagEvalReport | null | RagEvalBaselineResponse;
}

function RagMetricTable({ rows, baseline }: RagMetricTableProps) {
  const baselineRows = baseline ? buildMetricRows(baseline) : null;
  return (
    <table className="pa-table pa-metric-table" data-testid="rag-metric-table">
      <thead>
        <tr>
          <th>指标</th>
          <th>当前</th>
          <th>Baseline</th>
          <th>Δ</th>
          <th>方向</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const baseRow = baselineRows?.find((b) => b.key === row.key);
          const baseVal = baseRow?.value;
          const delta =
            baseVal !== undefined ? row.value - baseVal : undefined;
          const regress = isRegression(row, row.value, baseVal);
          return (
            <tr
              key={row.key}
              data-testid={`rag-metric-${row.key}`}
              data-regression={regress ? "yes" : "no"}
            >
              <td>{row.label}</td>
              <td>
                <strong>{fmt(row.value, row.unit)}</strong>
                <span className="pa-faint pa-tiny"> {row.unit}</span>
              </td>
              <td>
                {baseVal !== undefined ? fmt(baseVal, row.unit) : "—"}
              </td>
              <td>
                {delta !== undefined
                  ? (delta >= 0 ? "+" : "") + delta.toFixed(3)
                  : "—"}
              </td>
              <td>
                <Badge
                  tone={
                    regress
                      ? "err"
                      : row.direction === "up"
                        ? "ok"
                        : "warn"
                  }
                  testId={`rag-tone-${row.key}`}
                >
                  {row.direction === "up" ? "↑ 越大越好" : "↓ 越小越好"}
                </Badge>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function RagBaselineCard({
  baseline,
  loading,
  onRefresh,
}: {
  baseline: RagEvalBaselineResponse | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  return (
    <Card
      title="Baseline"
      testId="rag-baseline-card"
      footer={
        <Button
          variant="secondary"
          size="sm"
          onClick={onRefresh}
          data-testid="rag-baseline-refresh"
        >
          刷新 baseline
        </Button>
      }
    >
      {loading ? (
        <div className="pa-faint">加载中…</div>
      ) : baseline && baseline.aggregate_retrieval && baseline.aggregate_answer && baseline.aggregate_system ? (
        <div data-testid="rag-baseline-summary">
          <div className="pa-small pa-muted">
            run_id: <strong>{baseline.run_id}</strong>
          </div>
          <div className="pa-small pa-muted">
            Recall@5: {baseline.aggregate_retrieval.recall_at_5.toFixed(3)} ·
            Faithfulness: {baseline.aggregate_answer.faithfulness.toFixed(3)} ·
            Latency p95: {baseline.aggregate_system.latency_p95_ms.toFixed(0)}ms
          </div>
        </div>
      ) : (
        <div className="pa-faint" data-testid="rag-baseline-empty">
          暂无 baseline, 点击下方 "Run Eval" 跑一次后再保存
        </div>
      )}
    </Card>
  );
}

function RagRegressionAlert({ report }: { report: RagEvalReport | null }) {
  if (!report) return null;
  if (!report.regressions || report.regressions.length === 0) {
    return (
      <Card title="Regression Alert" testId="rag-regression-card">
        <Badge tone="ok" testId="rag-regression-ok">
          无回归
        </Badge>
      </Card>
    );
  }
  return (
    <Card title="Regression Alert" testId="rag-regression-card">
      <ul data-testid="rag-regression-list">
        {report.regressions.map((r, i) => (
          <li key={i} data-testid={`rag-regression-${i}`}>
            <Badge tone="err" testId={`rag-regression-tone-${i}`}>
              regress
            </Badge>{" "}
            {r}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function RagEvalDashboard({ testId }: { testId?: string }) {
  const [report, setReport] = useState<RagEvalReport | null>(null);
  const [baseline, setBaseline] = useState<RagEvalBaselineResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [loadingBaseline, setLoadingBaseline] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [seed, setSeed] = useState<RagEvalSeedLibraryResponse | null>(null);

  const refreshBaseline = async () => {
    setLoadingBaseline(true);
    try {
      const data = await apiClient.get<RagEvalBaselineResponse>(
        `/api/v1/projects/${PROJECT_ID}/paper-library/eval/baseline`,
      );
      setBaseline(data);
    } catch (e) {
      // baseline 缺失是常态, 不报错
      setBaseline(null);
    } finally {
      setLoadingBaseline(false);
    }
  };

  const runSeed = async () => {
    setError(null);
    try {
      const data = await apiClient.post<RagEvalSeedLibraryResponse>(
        `/api/v1/projects/${PROJECT_ID}/paper-library/eval/seed-library`,
        {},
      );
      setSeed(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const runEval = async () => {
    setRunning(true);
    setError(null);
    try {
      const body: RagEvalRunRequest = { llm_mock: true, scope: "all_papers" };
      const data = await apiClient.post<RagEvalRunResponse>(
        `/api/v1/projects/${PROJECT_ID}/paper-library/eval/run`,
        body,
      );
      setReport(data.report);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`${e.status} ${e.message}`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setRunning(false);
    }
  };

  useEffect(() => {
    refreshBaseline();
  }, []);

  const rows = report ? buildMetricRows(report) : [];

  return (
    <div className="pa-rag-eval" data-testid={testId ?? "rag-eval-dashboard"}>
      <Card
        title="RAG Eval"
        testId="rag-eval-card"
        footer={
          <div className="pa-interview-actions">
            <Button
              variant="secondary"
              size="sm"
              onClick={runSeed}
              data-testid="rag-seed-btn"
            >
              1. Seed Library
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={runEval}
              disabled={running}
              data-testid="rag-run-btn"
            >
              {running ? "运行中…" : "2. Run Eval"}
            </Button>
          </div>
        }
      >
        {seed ? (
          <div className="pa-small pa-muted" data-testid="rag-seed-info">
            <Badge tone="ok" testId="rag-seed-badge">seeded</Badge>{" "}
            {seed.paper_count} papers · {seed.chunk_count} chunks
          </div>
        ) : null}
        {error ? (
          <div className="pa-error pa-tiny" data-testid="rag-error">
            {error}
          </div>
        ) : null}
      </Card>
      <RagBaselineCard
        baseline={baseline}
        loading={loadingBaseline}
        onRefresh={refreshBaseline}
      />
      {report ? (
        <Card title="指标表" testId="rag-metric-card">
          <RagMetricTable rows={rows} baseline={baseline} />
        </Card>
      ) : (
        <Card title="指标表" testId="rag-metric-card">
          <div className="pa-faint" data-testid="rag-metric-empty">
            跑一次 Eval 后这里会显示 recall@5 / MRR / faithfulness 等指标
          </div>
        </Card>
      )}
      <RagRegressionAlert report={report} />
    </div>
  );
}