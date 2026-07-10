export type TaskRole =
  | "structured_extract"
  | "search_control"
  | "evidence_critic"
  | "novelty_draft"
  | "narrative_write"
  | "rag_answer"
  | "formatter";

export interface ProbedCapabilities {
  chat: boolean;
  json_object: boolean;
  json_schema: boolean;
  reasoning_envelope: boolean;
  streaming: boolean;
}

export interface ModelInfo {
  model_id: string;
  label: string | null;
  discovery_source: "auto" | "manual";
  probed_capabilities: ProbedCapabilities | null;
}

export interface ProviderProfile {
  provider_id: string;
  label: string;
  protocol: "openai_compatible" | "anthropic_like";
  base_url: string;
  api_key_set: boolean;
  secret_type: "session" | "local_vault";
  models: ModelInfo[];
  status: "active" | "invalid" | "disabled";
  config_version: string;
}

export interface ModelPolicyItem {
  role: TaskRole;
  primary: { provider_id: string; model_id: string };
  fallbacks: Array<{ provider_id: string; model_id: string }>;
  contract_version: string;
  temperature: number;
  allow_heuristic: boolean;
  max_provider_attempts: number;
  max_format_repairs: number;
}

export interface RunSnapshot {
  snapshot_id: string;
  call_id: string;
  timestamp: string;
  contract_id: string;
  contract_role: string;
  success: boolean;
  heuristic: boolean;
  providers_tried: number;
  repairs: number;
  tokens_in: number;
  tokens_out: number;
  error: string | null;
  policy_role?: string;
  policy_primary?: string;
  final_provider?: string;
  final_model?: string;
}

export const ALLOWED_MODEL_IDS = ["deepseek-v4-flash", "big-pickle"] as const;

export const TASK_ROLE_LABELS: Record<TaskRole, string> = {
  structured_extract: "结构化提取",
  search_control: "搜索控制",
  evidence_critic: "证据审核",
  novelty_draft: "创新草稿",
  narrative_write: "叙事写作",
  rag_answer: "RAG 问答",
  formatter: "JSON 修复",
};

export const TASK_ROLE_DESCRIPTIONS: Record<TaskRole, string> = {
  structured_extract: "topic_parser, verifier, dataset_extractor",
  search_control: "planner, SearchController, repair",
  evidence_critic: "low_bar, devils_advocate, novelty_review",
  novelty_draft: "innovation_extractor, contribution writing",
  narrative_write: "narrative_builder, report phrasing",
  rag_answer: "RAG QA",
  formatter: "JSON repair",
};

export interface ProviderListResponse {
  providers: ProviderProfile[];
}

export interface PolicyListResponse {
  policies: ModelPolicyItem[];
}

export interface SnapshotListResponse {
  snapshots: RunSnapshot[];
  stats: {
    total: number;
    success: number;
    failure: number;
    heuristic_fallbacks: number;
    total_repairs: number;
    total_tokens_in: number;
    total_tokens_out: number;
  };
}

export interface ProviderWizardState {
  step: number;
  label: string;
  protocol: "openai_compatible" | "anthropic_like";
  base_url: string;
  discover_result: "idle" | "loading" | "auto" | "manual";
  discovered_models: ModelInfo[];
  manual_model_id: string;
  selected_models: string[];
  probe_status: Record<string, Record<string, "pending" | "probing" | "pass" | "fail">>;
  role_bindings: Record<TaskRole, {
    primary_model: string;
    fallback_model: string;
    temperature: number;
  }>;
  saving: boolean;
  error: string | null;
}

export const WIZARD_STEPS = [
  { step: 1, label: "基本信息" },
  { step: 2, label: "连接设置" },
  { step: 3, label: "验证连接" },
  { step: 4, label: "模型发现" },
  { step: 5, label: "能力探测" },
  { step: 6, label: "角色绑定" },
  { step: 7, label: "保存" },
] as const;
