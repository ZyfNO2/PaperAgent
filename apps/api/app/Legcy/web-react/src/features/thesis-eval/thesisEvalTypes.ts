// Session 55: ThesisEval DTO (对齐 backend schemas_thesis_eval.py)
// ponytail: 字段名严格 1:1 对齐, 枚举直白, optional 显式 | null

export type VerifiedStatus = "verified" | "partial" | "failed";
export type Difficulty = "低-中" | "中" | "中-高" | "高";
export type AssessmentMode = "llm" | "heuristic";
export type GraduationFeasibility =
  | "可做"
  | "收缩后可做"
  | "可转向"
  | "暂缓"
  | "不建议";
export type SubsetName = "smoke_20" | "regression_60" | "hard_20" | "all_100";
export type ExperimentNeedTag =
  | "single_gpu_ok"
  | "cpu_or_light_gpu_ok"
  | "large_gpu_optional"
  | "h100_level_not_recommended"
  | "self_collected_dataset"
  | "public_dataset_available"
  | "hardware_platform_required"
  | "annotation_heavy"
  | "domain_data_permission_risk";
export type ThesisDomain =
  | "三维视觉/SLAM/点云"
  | "土木/交通基础设施损伤检测"
  | "工业缺陷检测/机器视觉"
  | "自动驾驶/交通感知"
  | "电力/轨交巡检视觉"
  | "工科AI/计算机视觉"
  | "机器人/机械臂实验系统"
  | "遥感/无人机目标检测"
  | "能源装备/故障诊断"
  | "医学/人体三维视觉";

export interface ThesisRecord {
  thesis_id: string;
  title: string;
  year: number | null;
  source_url: string;
  domain: ThesisDomain | null;
  abstract_snippet: string | null;
  verified_status: VerifiedStatus;
  fallback_used: boolean;
}

export interface EvidenceRef {
  // 后端 schemas.EvidenceRef 字段, 暂保最小
  source?: string;
  ref_id?: string;
  url?: string;
  snippet?: string;
}

export interface ThesisAssessment {
  thesis_id: string;
  record: ThesisRecord;
  experiment_needs: ExperimentNeedTag[];
  difficulty: Difficulty | null;
  cycle: string | null;
  repeatability: string | null;
  graduation_feasibility: GraduationFeasibility | null;
  reality_tier: string | null;
  evidence_refs: EvidenceRef[];
  unsupported_claims: string[];
  risk_tags: string[];
  assessment_mode: AssessmentMode;
  confidence: number;
}

export interface ThesisEvalResult {
  thesis_id: string;
  predicted: ThesisAssessment;
  gold: Record<string, unknown>;
  task_metrics: Record<string, number>;
  hits: Record<string, boolean | number>;
}

export interface ThesisEvalReport {
  run_id: string;
  created_at: string;
  subset: SubsetName;
  thesis_count: number;
  results: ThesisEvalResult[];
  aggregate_metrics: Record<string, number>;
  baseline_diff: Record<string, number>;
  regressions: string[];
}

export interface ThesisAssessRequest {
  url: string;
  llm_mock?: boolean;
}

// baseline GET: { baseline: ThesisEvalReport | null, message: str }
export interface ThesisEvalBaselineResponse {
  baseline: ThesisEvalReport | null;
  message: string;
}