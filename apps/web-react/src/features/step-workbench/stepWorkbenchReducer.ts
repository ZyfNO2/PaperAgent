// Session 54: StepWorkbench reducer
// ponytail: 状态机 = 当前 activeStep + steps[] + trace/llm/tools + chat + interview flags
// 关键不变式: 切换 activeStep 不清空 trace/llm/chat

import {
  STATUS,
  initSteps,
  type StepState,
  type StepStatus,
  type TraceEvent,
  type LlmEvent,
  type ToolUseEvent,
  type ChatMessage,
} from "./stepTypes";
import { DEMO_CASE_STEP_RESULTS } from "../interview-mode/interviewData";

let _seq = 0;
const nextSeq = () => ++_seq;
const newId = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

export interface WorkbenchState {
  activeStepIndex: number;
  steps: StepState[];
  trace: TraceEvent[];
  llm: LlmEvent[];
  tools: ToolUseEvent[];
  chat: ChatMessage[];
  streamPhase: "idle" | "streaming" | "paused" | "done";
  commandPreview: { intent: string; description: string } | null;
  demoLoaded: boolean;
  demoTopic: string;
  demoDisclaimer: string;
  chatDraft: string;
  topic: string;
}

export type WorkbenchAction =
  | { type: "SET_ACTIVE_STEP"; index: number }
  | { type: "SET_STEP_STATUS"; index: number; status: StepStatus; staleReason?: string }
  | { type: "SET_STEP_RESULT"; index: number; result: Record<string, unknown> }
  | { type: "APPEND_TRACE"; kind: string; text: string; step: number | null }
  | { type: "APPEND_LLM"; kind: LlmEvent["kind"]; text: string; step: number | null }
  | { type: "APPEND_TOOL"; tool: string; purpose: string; source: string; step: number | null }
  | { type: "ADD_CHAT"; msg: Omit<ChatMessage, "id" | "ts"> }
  | { type: "SET_CHAT_DRAFT"; draft: string }
  | { type: "SET_STREAM_PHASE"; phase: WorkbenchState["streamPhase"] }
  | { type: "SET_COMMAND_PREVIEW"; preview: WorkbenchState["commandPreview"] }
  | { type: "LOAD_DEMO_CASE"; topic: string; disclaimer: string }
  | { type: "SET_TOPIC"; topic: string };

export function initState(): WorkbenchState {
  return {
    activeStepIndex: 0,
    steps: initSteps(),
    trace: [],
    llm: [],
    tools: [],
    chat: [],
    streamPhase: "idle",
    commandPreview: null,
    demoLoaded: false,
    demoTopic: "",
    demoDisclaimer: "",
    chatDraft: "",
    topic: "",
  };
}

export function workbenchReducer(
  state: WorkbenchState,
  action: WorkbenchAction,
): WorkbenchState {
  switch (action.type) {
    case "SET_ACTIVE_STEP":
      return { ...state, activeStepIndex: action.index };
    case "SET_STEP_STATUS": {
      const steps = state.steps.map((s, i) =>
        i === action.index
          ? {
              ...s,
              status: action.status,
              staleReason:
                action.status === STATUS.STALE
                  ? (action.staleReason ?? s.staleReason)
                  : null,
            }
          : s,
      );
      return { ...state, steps };
    }
    case "SET_STEP_RESULT": {
      const steps = state.steps.map((s, i) =>
        i === action.index ? { ...s, result: action.result } : s,
      );
      return { ...state, steps };
    }
    case "APPEND_TRACE":
      return {
        ...state,
        trace: [
          ...state.trace,
          {
            seq: nextSeq(),
            kind: action.kind,
            text: action.text,
            step: action.step,
          },
        ],
      };
    case "APPEND_LLM":
      return {
        ...state,
        llm: [
          ...state.llm,
          {
            seq: nextSeq(),
            kind: action.kind,
            text: action.text,
            step: action.step,
          },
        ],
      };
    case "APPEND_TOOL":
      return {
        ...state,
        tools: [
          ...state.tools,
          {
            seq: nextSeq(),
            tool: action.tool,
            purpose: action.purpose,
            source: action.source,
            step: action.step,
          },
        ],
      };
    case "ADD_CHAT":
      return {
        ...state,
        chat: [
          ...state.chat,
          { id: newId(), ts: Date.now(), ...action.msg },
        ],
      };
    case "SET_CHAT_DRAFT":
      return { ...state, chatDraft: action.draft };
    case "SET_STREAM_PHASE":
      return { ...state, streamPhase: action.phase };
    case "SET_COMMAND_PREVIEW":
      return { ...state, commandPreview: action.preview };
    case "LOAD_DEMO_CASE": {
      const steps = state.steps.map((s, i) => ({
        ...s,
        status: STATUS.COMPLETED,
        result: DEMO_CASE_STEP_RESULTS[i] ?? s.result,
      }));
      return {
        ...state,
        steps,
        demoLoaded: true,
        demoTopic: action.topic,
        demoDisclaimer: action.disclaimer,
        topic: action.topic,
      };
    }
    case "SET_TOPIC":
      return { ...state, topic: action.topic };
    default:
      return state;
  }
}

// ponytail: helper 让 UI 用一行流式追加
export function appendAssistantReply(
  _state: WorkbenchState,
  text: string,
  step: number | null,
): WorkbenchAction {
  return { type: "APPEND_LLM", kind: "assistant_reply", text, step };
}
