// Session 54: reducer 状态机测试
import { describe, it, expect } from "vitest";
import {
  initState,
  workbenchReducer,
} from "./stepWorkbenchReducer";
import { STATUS, STEPS } from "./stepTypes";

describe("workbenchReducer", () => {
  it("initial state has 5 steps locked", () => {
    const s = initState();
    expect(s.steps).toHaveLength(5);
    expect(s.steps.every((x) => x.status === STATUS.LOCKED)).toBe(true);
    expect(s.activeStepIndex).toBe(0);
  });

  it("SET_ACTIVE_STEP 不清空 trace/llm/chat", () => {
    const s0 = initState();
    const s1 = workbenchReducer(s0, {
      type: "APPEND_TRACE",
      kind: "step_start",
      text: "x",
      step: 0,
    });
    const s2 = workbenchReducer(s1, { type: "SET_ACTIVE_STEP", index: 2 });
    expect(s2.activeStepIndex).toBe(2);
    expect(s2.trace).toEqual(s1.trace);
  });

  it("SET_STEP_STATUS 更新单步, staleReason 处理", () => {
    const s0 = initState();
    const s1 = workbenchReducer(s0, {
      type: "SET_STEP_STATUS",
      index: 1,
      status: STATUS.RUNNING,
    });
    expect(s1.steps[1].status).toBe(STATUS.RUNNING);
    const s2 = workbenchReducer(s1, {
      type: "SET_STEP_STATUS",
      index: 1,
      status: STATUS.STALE,
      staleReason: "evidence retracted",
    });
    expect(s2.steps[1].staleReason).toBe("evidence retracted");
    const s3 = workbenchReducer(s2, {
      type: "SET_STEP_STATUS",
      index: 1,
      status: STATUS.COMPLETED,
    });
    // ponytail: 非 STALE 状态清空 staleReason
    expect(s3.steps[1].staleReason).toBeNull();
  });

  it("LOAD_DEMO_CASE 把 5 步置为 completed, 并注入结果", () => {
    const s0 = initState();
    const s1 = workbenchReducer(s0, {
      type: "LOAD_DEMO_CASE",
      topic: "demo topic",
      disclaimer: "demo disclaimer",
    });
    expect(s1.demoLoaded).toBe(true);
    expect(s1.steps[0].status).toBe(STATUS.COMPLETED);
    expect(s1.steps[0].result).toBeTruthy();
    expect(s1.steps[4].status).toBe(STATUS.COMPLETED);
  });

  it("ADD_CHAT 分配 id/ts", () => {
    const s0 = initState();
    const s1 = workbenchReducer(s0, {
      type: "ADD_CHAT",
      msg: { role: "user", text: "修改 step 3" },
    });
    expect(s1.chat).toHaveLength(1);
    expect(s1.chat[0].id).toMatch(/^msg-/);
    expect(s1.chat[0].text).toBe("修改 step 3");
  });

  it("SET_STEP_RESULT 注入 result 但不动 status", () => {
    const s0 = initState();
    const s1 = workbenchReducer(s0, {
      type: "SET_STEP_RESULT",
      index: 0,
      result: { direction: "test" },
    });
    expect(s1.steps[0].result).toEqual({ direction: "test" });
    expect(s1.steps[0].status).toBe(STATUS.LOCKED);
  });

  it("STEPS 顺序与 key 正确", () => {
    expect(STEPS.map((s) => s.key)).toEqual([
      "topic_understanding",
      "keyword_breakdown",
      "search_candidates",
      "feasibility",
      "proposal",
    ]);
  });
});
