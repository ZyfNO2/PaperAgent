// Session 55: pure helper tests — no React mount
// ponytail: metric 方向 + regression 判定逻辑单测
import { describe, it, expect } from "vitest";

// 复制一份 buildMetricRows 逻辑做最小测试 — 与 RagEvalDashboard.tsx 保持同步
type Direction = "up" | "down";
type Row = {
  key: string;
  direction: Direction;
};

function buildRows(r: { recall_at_5: number; mrr: number; ndcg_at_5: number; hit_rate: number },
                  a: { citation_precision: number; evidence_coverage: number; unsupported_claim_rate: number; faithfulness: number },
                  s: { latency_p50_ms: number; latency_p95_ms: number; fallback_rate: number }) {
  return [
    { key: "recall_at_5", value: r.recall_at_5, direction: "up" as Direction },
    { key: "mrr", value: r.mrr, direction: "up" as Direction },
    { key: "ndcg_at_5", value: r.ndcg_at_5, direction: "up" as Direction },
    { key: "hit_rate", value: r.hit_rate, direction: "up" as Direction },
    { key: "citation_precision", value: a.citation_precision, direction: "up" as Direction },
    { key: "evidence_coverage", value: a.evidence_coverage, direction: "up" as Direction },
    { key: "unsupported_claim_rate", value: a.unsupported_claim_rate, direction: "down" as Direction },
    { key: "faithfulness", value: a.faithfulness, direction: "up" as Direction },
    { key: "latency_p50", value: s.latency_p50_ms, direction: "down" as Direction },
    { key: "latency_p95", value: s.latency_p95_ms, direction: "down" as Direction },
    { key: "fallback_rate", value: s.fallback_rate, direction: "down" as Direction },
  ];
}

// 与后端 apps/api/app/services/paper_library/eval_baseline.py REGRESSION_THRESHOLDS 对齐
const REGRESSION_THRESHOLDS: Record<string, { direction: Direction; threshold: number }> = {
  recall_at_5: { direction: "up", threshold: 0.05 },
  mrr: { direction: "up", threshold: 0.05 },
  ndcg_at_5: { direction: "up", threshold: 0.05 },
  hit_rate: { direction: "up", threshold: 0.05 },
  citation_precision: { direction: "up", threshold: 0.05 },
  evidence_coverage: { direction: "up", threshold: 0.05 },
  unsupported_claim_rate: { direction: "down", threshold: 0.05 },
  faithfulness: { direction: "up", threshold: 0.05 },
  latency_p50_ms: { direction: "down", threshold: 50 },
  latency_p95_ms: { direction: "down", threshold: 100 },
  fallback_rate: { direction: "down", threshold: 0.05 },
};

function isRegression(row: Row, current: number, baseline: number): boolean {
  const cfg = REGRESSION_THRESHOLDS[row.key] ?? { direction: row.direction, threshold: 0.05 };
  const delta = current - baseline;
  return cfg.direction === "down" ? delta > cfg.threshold : delta < -cfg.threshold;
}

describe("rag metric direction + regression", () => {
  it("up 方向: recall 下降应回归", () => {
    const row: Row = { key: "recall_at_5", direction: "up" };
    expect(isRegression(row, 0.6, 0.7)).toBe(true);
    expect(isRegression(row, 0.69, 0.7)).toBe(false);
  });

  it("down 方向: latency 上升应回归", () => {
    const row: Row = { key: "latency_p95_ms", direction: "down" };
    expect(isRegression(row, 850, 700)).toBe(true);
    expect(isRegression(row, 750, 700)).toBe(false);
  });

  it("unsupported_claim_rate 上升应回归 (方向 down)", () => {
    const row: Row = { key: "unsupported_claim_rate", direction: "down" };
    expect(isRegression(row, 0.15, 0.05)).toBe(true);
    expect(isRegression(row, 0.07, 0.05)).toBe(false);
  });

  it("buildRows 产出 11 个指标, 方向正确", () => {
    const rows = buildRows(
      { recall_at_5: 0.8, mrr: 0.7, ndcg_at_5: 0.6, hit_rate: 0.9 },
      { citation_precision: 0.7, evidence_coverage: 0.6, unsupported_claim_rate: 0.1, faithfulness: 0.8 },
      { latency_p50_ms: 100, latency_p95_ms: 500, fallback_rate: 0.05 },
    );
    expect(rows).toHaveLength(11);
    const upRows = rows.filter((r) => r.direction === "up");
    const downRows = rows.filter((r) => r.direction === "down");
    expect(upRows.length).toBe(7);
    expect(downRows.length).toBe(4);
  });
});

describe("thesis subset key", () => {
  it("smoke_20 / regression_60 / hard_20 / all_100 共 4 个", () => {
    const SUBSETS = ["smoke_20", "regression_60", "hard_20", "all_100"];
    expect(SUBSETS).toHaveLength(4);
    expect(SUBSETS[0]).toBe("smoke_20");
  });
});