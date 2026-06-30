// Session 62: GraduationDirection types — 对齐后端 schemas_graduation_direction.py
// ponytail: 不引 zod, 用 interface 与运行时断言。

export type RiskLevel = "low" | "medium" | "high";

export interface BaselineRecommendation {
  name: string;
  rationale: string;
  required_data: string;
  reproducibility: "low" | "medium" | "high";
  estimated_compute: string;
  risks: string[];
}

export interface ExtensionModule {
  name: string;
  attach_to: string;
  problem_solved: string;
  ablation_plan: string;
  effort: "S" | "M" | "L";
  risks: string[];
}

export interface EvidenceBundleRef {
  ref_type: "paper" | "dataset" | "repo" | "rag_chunk";
  ref_id: string;
  title: string;
  url?: string | null;
  quote?: string | null;
}

export interface EvidenceBundle {
  papers: EvidenceBundleRef[];
  datasets: EvidenceBundleRef[];
  repos: EvidenceBundleRef[];
  rag_refs: EvidenceBundleRef[];
  gaps: string[];
}

export interface ScoringBreakdownItem {
  key: string;
  label: string;
  score: number;
  weight: number;
  note: string;
}

export interface GraduationDirection {
  direction_id: string;
  title: string;
  research_object: string;
  task: string;
  method_route: string;
  why_graduation_friendly: string[];
  fallback_route: string;
  score: number;
  risk_level: RiskLevel;
  evidence_bundle: EvidenceBundle;
  recommended_baselines: BaselineRecommendation[];
  extension_modules: ExtensionModule[];
  scoring_breakdown: ScoringBreakdownItem[];
}

export interface DirectionDecisionReport {
  project_id: string;
  topic: string;
  recommended_direction_id: string;
  directions: GraduationDirection[];
  stop_reason: string;
  generated_at: string;
  evidence_sources: Record<string, number>;
  warnings: string[];
}