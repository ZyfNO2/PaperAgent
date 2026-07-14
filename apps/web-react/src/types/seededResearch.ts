// ===== Seeded Research Pipeline 类型定义 =====
// 对应 Re8.0 后端 Seeded Research pipeline 的前端类型契约。
// fixture 来源：artifacts/re8_0/seeded_demo_vit_dr_rerun2.json

/** 种子论文在研究中的角色 */
export type SeedRole =
  | 'classic_anchor'
  | 'current_sota_candidate'
  | 'reproduction_target'
  | 'parallel_inspiration'
  | 'survey_reference';

/** 种子录入的输入形式 */
export type SeedInputForm = 'doi' | 'arxiv' | 'url' | 'pdf' | 'citation' | 'title';

/** 候选种子输入（前端录入表单数据） */
export interface CandidateSeedInput {
  seed_id: string;
  input_form: SeedInputForm;
  doi?: string;
  arxiv_id?: string;
  url?: string;
  title?: string;
  authors?: string[];
  year?: number;
  pdf_path?: string;
  role: SeedRole;
  raw_input?: Record<string, unknown>;
}

/** 种子核验后的卡片（来自后端 seed_audit 阶段） */
export interface SeedCard {
  seed_id: string;
  resolved_title: string;
  existence_status: 'verified' | 'ambiguous' | 'not_found';
  role: SeedRole;
  repair_hint?: string;
}

/** 单个 Reflection Gate 的裁决 */
export type GateVerdict = 'pass' | 'revise' | 'unresolved';

/** Gate 结果（含轮次与理由） */
export interface GateResult {
  verdict: GateVerdict;
  round_idx: number;
  generated_by: 'llm' | 'rule' | 'skip' | 'reuse';
  rationale: string;
  re_search_requests?: string[];
  unresolved_gaps?: string[];
  /** Re8.2 WP3: Seed Audit Gate 结构化 reason code 与诊断字段 */
  reason_code?: string;
  seed_id?: string;
  candidate_count?: number;
  top_score?: number;
  repair_target?: string;
  /** Re8.1 WP5: full round-by-round trajectory for Gate repair cycle display */
  all_rounds?: Array<{
    round_idx: number;
    verdict: GateVerdict;
    generated_by: 'llm' | 'rule' | 'skip' | 'reuse';
    rationale: string;
    reason_code?: string;
  }>;
}

/** Decision Fusion 融合后的最终裁决 */
export type FusedVerdict = 'GO' | 'CONDITIONAL' | 'RISKY' | 'BLOCKED';

/** Evidence Gap 状态 */
export interface EvidenceGap {
  gap_id: string;
  gap_type: string;
  status: 'open' | 'satisfied' | 'partially_satisfied';
  description?: string;
}

/** Tailor 阶段产出的方法摘要 */
export interface TailoredMethod {
  verdict?: string;
  core_method?: string;
  contribution_type?: string;
  baseline_model?: string;
  ablation_matrix?: unknown[];
}

/** Final Research Package（理想结构，完整版） */
export interface FinalResearchPackage {
  seed_audit_summary: unknown;
  tailor_summary: unknown;
  gate_results: Record<string, GateResult[]>;
  ledger_entries: unknown[];
  evidence_gap_status: EvidenceGap[];
  falsifiable_hypothesis: string;
  fused_verdict: { verdict: FusedVerdict; rationale: string };
}

/** 运行模式 */
export type RunMode = 'full_agent' | 'lite_chain' | 'offline_replay';

/** 网络策略 */
export type NetworkPolicy = 'online' | 'offline';

/**
 * Seeded Demo 运行结果摘要。
 * 对应 fixture 文件 artifacts/re8_0/seeded_demo_vit_dr_rerun2.json 的顶层结构。
 */
export interface SeededDemoResult {
  case_key: string;
  topic: string;
  description?: string;
  n_seeds_input: number;
  mode: string;
  status: string;
  elapsed_s: number;
  error: string | null;
  runtime_pass: boolean;
  contract_pass: boolean;
  contract_pass_reasons: string[];
  quality_pass: boolean;
  quality_pass_reasons: string[];
  final_rec?: {
    topic?: string;
    n_papers?: number;
    n_baseline?: number;
    n_parallel?: number;
    n_dataset?: number;
    n_repo?: number;
    n_work_packages?: number;
    low_bar_status?: string;
  };
  seed_cards: SeedCard[];
  n_trace_events?: number;
  n_gate_traces?: number;
  providers_used?: Record<string, number>;
  gate_seed_audit_gate: GateResult;
  gate_tailor_gate: GateResult;
  gate_final_review_gate: GateResult;
  n_ledger_entries?: number;
  n_react_actions?: number;
  n_errors?: number;
  error_samples?: string[];
  n_verified_papers?: number;
  n_search_steps?: number;
  tailored_verdict?: string;
  tailored_ablation_rows?: number;
  tailored_method_summary: TailoredMethod;
  novelty_review_verdict?: string;
  has_falsifiable_hypothesis?: boolean;
  hypothesis_preview?: string;
  n_evidence_gaps?: number;
  gap_statuses?: Record<string, number>;
  fused_verdict: FusedVerdict;
  fused_verdict_rationale?: string;
  final_research_package_sections: string[];
  final_research_package_section_count?: number;
  final_research_package_missing_sections?: string[];
  final_rec_fused_verdict?: FusedVerdict;
  final_rec_has_research_package?: boolean;
  repair_cycles_detected?: unknown[];
  n_repair_cycles?: number;
  /** Re8.1 WP5: honest error categories from backend (fused_blocked / gate_unresolved:* / seed_ambiguous / seed_not_found / network_offline) */
  error_categories?: string[];
  /** Re8.1 WP5: case_id from real backend run (alias of case_key) */
  case_id?: string;
  /** Re8.1 WP5: network policy actually applied */
  network_policy?: 'online' | 'offline';
  /** Re8.1 WP5: run mode actually applied */
  run_mode?: string;
  /** Re8.1 WP5: entry mode actually applied */
  entry_mode?: string;
}
