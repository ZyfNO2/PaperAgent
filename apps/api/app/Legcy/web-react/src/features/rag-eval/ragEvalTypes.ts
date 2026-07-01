// Session 55: RAG Eval DTO (对齐 backend schemas_paper_rag_eval.py)
// ponytail: 字段名严格 1:1 对齐, optional 显式 | null, 不在组件里临时猜字段

export type RetrievalMode = "llm" | "fallback";

export interface RetrievalMetrics {
  recall_at_5: number;
  mrr: number;
  ndcg_at_5: number;
  hit_rate: number;
}

export interface AnswerMetrics {
  citation_precision: number;
  evidence_coverage: number;
  unsupported_claim_rate: number;
  faithfulness: number;
}

export interface SystemMetrics {
  latency_p50_ms: number;
  latency_p95_ms: number;
  total_questions: number;
  fallback_rate: number;
}

export interface RagEvalItem {
  question_id: string;
  paper_id: string;
  question: string;
  retrieved_chunks: string[];
  cited_chunks: string[];
  answer: string;
  retrieval_metrics: RetrievalMetrics;
  answer_metrics: AnswerMetrics;
  latency_ms: number;
  retrieval_mode: RetrievalMode;
}

export interface RagEvalReport {
  run_id: string;
  created_at: string; // ISO datetime
  items: RagEvalItem[];
  aggregate_retrieval: RetrievalMetrics;
  aggregate_answer: AnswerMetrics;
  aggregate_system: SystemMetrics;
  baseline_diff: Record<string, number>;
  regressions: string[];
}

export interface RagEvalRunResponse {
  report: RagEvalReport;
}

export interface RagEvalSeedLibraryResponse {
  project_id: string;
  paper_count: number;
  chunk_count: number;
  message: string;
}

export interface RagEvalRunRequest {
  fixtures_path?: string | null;
  scope?: "all_papers" | "accepted_papers" | "specific";
  paper_ids?: string[] | null;
  llm_mock?: boolean;
}

// baseline GET: load_baseline() 返回 baseline dict 直接 (无 present 字段)
// 判 present: 看 aggregate_retrieval 是否存在
export type RagEvalBaselineResponse = Partial<RagEvalReport> & {
  baseline_run_id?: string;
};