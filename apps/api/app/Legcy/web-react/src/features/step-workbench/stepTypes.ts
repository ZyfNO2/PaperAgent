// Session 54: StepWorkbench 数据契约 + 状态机
// ponytail: 5 步 + 8 status 完整从旧 step_workbench.js 移植, demo case 抽关键 5 步结果

export const STATUS = {
  LOCKED: "locked",
  RUNNING: "running",
  PAUSED: "paused_for_review",
  NEEDS_REVISION: "needs_revision",
  APPROVED: "approved",
  COMPLETED: "completed",
  FAILED: "failed",
  STALE: "stale",
} as const;
export type StepStatus = (typeof STATUS)[keyof typeof STATUS];

export const STATUS_LABEL: Record<string, string> = {
  locked: "未解锁",
  running: "进行中",
  paused_for_review: "等待确认",
  needs_revision: "需要修改",
  approved: "已确认",
  completed: "已完成",
  failed: "失败",
  stale: "stale",
};

export const INTERVIEW_MODE = {
  LITE: "lite",
  INTERVIEW: "interview",
} as const;
export type InterviewMode = (typeof INTERVIEW_MODE)[keyof typeof INTERVIEW_MODE];

export interface StepDef {
  index: number;
  key: string;
  title: string;
  icon: string;
}

export interface StepState extends StepDef {
  status: StepStatus;
  staleReason: string | null;
  result: Record<string, unknown> | null;
}

export interface TraceEvent {
  seq: number;
  kind: string;
  text: string;
  step: number | null;
  meta?: Record<string, unknown>;
}

export interface LlmEvent {
  seq: number;
  kind: "assistant_reply" | "assistant_thought" | "user_input" | "command_preview";
  text: string;
  step: number | null;
  meta?: Record<string, unknown>;
}

export interface ToolUseEvent {
  seq: number;
  tool: string;
  purpose: string;
  source: string;
  step: number | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  intentKind?: "add" | "remove" | "modify" | "query";
  preview?: string;
  ts: number;
}

export const STEPS: StepDef[] = [
  { index: 0, key: "topic_understanding", title: "题目理解", icon: "1" },
  { index: 1, key: "keyword_breakdown", title: "关键词拆解", icon: "2" },
  { index: 2, key: "search_candidates", title: "检索计划与候选证据", icon: "3" },
  { index: 3, key: "feasibility", title: "可行性判断", icon: "4" },
  { index: 4, key: "proposal", title: "开题建议", icon: "5" },
];

export function buildStepState(): StepState {
  return {
    index: 0,
    key: "",
    title: "",
    icon: "",
    status: STATUS.LOCKED,
    staleReason: null,
    result: null,
  };
}

export function initSteps(): StepState[] {
  return STEPS.map((s) => ({
    ...s,
    status: STATUS.LOCKED,
    staleReason: null,
    result: null,
  }));
}
