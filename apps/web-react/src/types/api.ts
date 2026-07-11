// ===== Research State =====
export interface ResearchState {
  case_id: string;
  topic: string;
  topic_atoms?: TopicAtoms;
  verified_papers?: Paper[];
  repo_candidates?: RepoCandidate[];
  dataset_candidates?: DatasetCandidate[];
  feasibility_report?: FeasibilityReport;
  review_report?: ReviewReport;
  innovation_points?: InnovationPoint[];
  research_narrative?: ResearchNarrative;
  optimization_directions?: OptimizationDirection[];
  work_packages?: WorkPackage[];
  evidence_graph?: EvidenceGraph;
  trace_events?: TraceEvent[];
  [key: string]: unknown;
}

export interface TopicAtoms {
  method?: string[];
  task?: string[];
  object?: string[];
  domain?: string[];
}

export interface Paper {
  title: string;
  authors?: string[];
  year?: number | null;
  doi?: string;
  arxiv_id?: string;
  url?: string;
  abstract?: string;
  source?: string;
  verdict?: 'accept' | 'weak_reject' | 'reject';
  verification_verdict?: string;
  hit_keywords?: string[];
  citation_count?: number;
  relation_to_topic?: string;
  relevance_score?: number;
}

export interface RepoCandidate {
  full_name?: string;
  url: string;
  stars?: number;
  description?: string;
  language?: string;
  from_paper?: string;
}

export interface DatasetCandidate {
  name: string;
  url?: string;
  source?: string;
  description?: string;
}

export interface FeasibilityReport {
  score: number;
  verdict?: string;
  tier?: string;
  reason?: string;
  reasoning?: string;
  strengths?: string[];
  risks?: string[];
  degradation_paths?: string[];
}

export interface ReviewReport {
  overall_verdict?: string;
  review_status?: string;
  dimension_scores?: DimensionScore[];
  dimensions?: Record<string, number>;
  fabrication_alerts?: string[];
  risks_identified?: string[];
  risks?: string[];
}

export interface DimensionScore {
  dimension: string;
  score: number;
  verdict: string;
  reason: string;
}

export interface InnovationPoint {
  title?: string;
  point?: string;
  description?: string;
}

export interface ResearchNarrative {
  three_problems?: Array<{ problem: string; evidence: string; from_paper: string }>;
  nick_model_name?: string;
  narrative_summary?: string;
  abstract_draft?: string;
  chapter_outline?: Record<string, { title: string; sections: string }>;
}

export interface OptimizationDirection {
  direction?: string;
  rationale?: string;
  path?: string;
  name?: string;
  purpose?: string;
}

export interface WorkPackage {
  title?: string;
  name?: string;
  description?: string;
  gap?: string;
}

export interface EvidenceGraph {
  nodes: EvidenceNode[];
  edges: EvidenceEdge[];
}

export interface EvidenceNode {
  id: string;
  type: string;
  label?: string;
}

export interface EvidenceEdge {
  from: string;
  to: string;
  label?: string;
}

// ===== SSE Events =====
export type SSEEventType =
  | 'search_started'
  | 'node_current'
  | 'papers_update'
  | 'papers_verified'
  | 'adapter_result'
  | 'adapter_status'
  | 'search_completed'
  | 'filter_result'
  | 'verify_completed'
  | 'candidate_count'
  | 'expansion_started'
  | 'expansion_completed'
  | 'repos_update'
  | 'datasets_update'
  | 'node_complete'
  | 'done'
  | 'error';

export interface SSEEventData {
  [key: string]: unknown;
}

export interface SSEEvent {
  type: SSEEventType;
  data: SSEEventData;
}

// ===== SourcePolicy =====
export interface SourcePolicyEntry {
  enabled: boolean;
  status: 'enabled' | 'skipped' | 'rate_limited' | 'failed';
  concurrency: number;
  retries: number;
  timeout: number;
}

// ===== Trace =====
export interface TraceEvent {
  node: string;
  started_at: string;
  ended_at?: string;
  elapsed_s: number;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  tool_calls: unknown[];
  errors: string[];
  state_keys: string[];
  provider?: string;
}

// ===== Case Status =====
export interface CaseStatus {
  status: string;
  current_node?: string;
  n_trace_events?: number;
  elapsed_s?: number;
  n_papers?: number;
  n_packages?: number;
  n_nodes?: number;
  error?: string;
  message?: string;
  has_state_json: boolean;
  has_trace_json: boolean;
  has_evidence_graph_json: boolean;
}

export interface CaseListItem {
  case_id: string;
  file_size: number;
  mtime: number;
  status: string;
}
