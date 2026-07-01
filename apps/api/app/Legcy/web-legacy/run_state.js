// Session 21: Step Deck 状态机 (前端, 纯 JS, 不依赖后端).
//
// 实现 SOP §7 的前端状态机:
// - runState: { runId, currentStep, steps{}, cards{}, gates{}, eventBuffer[], lastSeq }
// - StepStatus: pending | streaming | awaiting_review | approved | revising | completed | failed
// - 标准事件: run_started / step_started / token_delta / card_delta /
//            artifact_ready / step_pause / user_patch_required / step_resumed /
//            run_completed / run_failed
//
// 本轮 (21-a) 只做 UI 骨架, 不做 LLM 调用, 数据来自 mock 事件流.

(function (global) {
  "use strict";

  // ---------- 状态机常量 ----------

  const STEP_KEYS = [
    "input",                // 0. 输入题目
    "topic_understanding",  // 1. 题目理解
    "keyword_review",       // 2. 关键词 Gate
    "query_plan",           // 3. 检索计划
    "candidates",           // 4. 候选证据
    "workspace",            // 5. 证据工作台
    "feasibility",          // 6. 可行性
    "proposal",             // 7. 开题报告推荐
    "report_quality",       // 8. 报告质量
  ];

  const STEP_LABELS = {
    input:                { num: "0", title: "输入题目",       icon: "📝" },
    topic_understanding:  { num: "1", title: "题目理解",       icon: "💡" },
    keyword_review:       { num: "2", title: "关键词审查",     icon: "🔑" },
    query_plan:           { num: "3", title: "检索计划",       icon: "🔎" },
    candidates:           { num: "4", title: "候选证据",       icon: "📚" },
    workspace:            { num: "5", title: "证据工作台",     icon: "🗂️" },
    feasibility:          { num: "6", title: "可行性判断",     icon: "⚖️" },
    proposal:             { num: "7", title: "开题报告推荐",   icon: "📋" },
    report_quality:       { num: "8", title: "报告质量复核",   icon: "🛡️" },
  };

  const STATUS = Object.freeze({
    PENDING:          "pending",
    STREAMING:        "streaming",
    AWAITING_REVIEW:  "awaiting_review",
    APPROVED:         "approved",
    REVISING:         "revising",
    COMPLETED:        "completed",
    FAILED:           "failed",
  });

  const STATUS_LABEL = {
    pending:         "待开始",
    streaming:       "生成中",
    awaiting_review: "待审查",
    approved:        "已通过",
    revising:        "修订中",
    completed:       "已完成",
    failed:          "失败",
  };

  // ---------- RunState ----------

  function createRunState() {
    return {
      runId: null,
      currentStep: "input",
      steps: {},     // { [stepKey]: { status, text, blocks, artifacts, userPatch, lastSeq } }
      cards: {},     // { [cardId]: { id, stepKey, type, props, html } }
      gates: {},     // { [stepKey]: { reason, availableActions, openedAt } }
      eventBuffer: [], // ordered events (for replay)
      lastSeq: 0,
      isStreaming: false,
      hasApprovedGate2: false,
    };
  }

  function ensureStep(runState, stepKey) {
    if (!runState.steps[stepKey]) {
      runState.steps[stepKey] = {
        status: STATUS.PENDING,
        text: "",
        blocks: [],
        artifacts: [],
        userPatch: null,
        lastSeq: 0,
      };
    }
    return runState.steps[stepKey];
  }

  // ---------- 标准事件协议 (SOP §6.2) ----------

  const EVENT_TYPES = [
    "run_started", "step_started", "token_delta", "card_delta",
    "artifact_ready", "step_pause", "user_patch_required",
    "step_resumed", "run_completed", "run_failed",
  ];

  function makeEvent(type, payload, runState) {
    runState.lastSeq += 1;
    return {
      event_id: "evt_" + String(runState.lastSeq).padStart(3, "0"),
      seq: runState.lastSeq,
      run_id: runState.runId,
      project_id: window.PaperAgentState && window.PaperAgentState.projectId || null,
      step_key: runState.currentStep,
      event_type: type,
      status: null,
      payload: payload || {},
      ts: new Date().toISOString(),
    };
  }

  function applyEvent(runState, evt) {
    runState.eventBuffer.push(evt);
    if (evt.seq > runState.lastSeq) runState.lastSeq = evt.seq;

    const step = ensureStep(runState, evt.step_key || runState.currentStep);
    step.lastSeq = evt.seq;

    switch (evt.event_type) {
      case "run_started":
        runState.runId = evt.run_id;
        step.status = STATUS.STREAMING;
        break;
      case "step_started":
        runState.currentStep = evt.step_key;
        ensureStep(runState, evt.step_key).status = STATUS.STREAMING;
        break;
      case "token_delta": {
        step.text = (step.text || "") + (evt.payload && evt.payload.text || "");
        step.status = STATUS.STREAMING;
        break;
      }
      case "card_delta": {
        const cardId = (evt.payload && evt.payload.id) || ("card_" + evt.seq);
        const blockType = (evt.payload && evt.payload.component) || "UnknownCard";
        const blockProps = (evt.payload && evt.payload.props) || {};
        runState.cards[cardId] = {
          id: cardId,
          stepKey: evt.step_key,
          type: blockType,
          props: blockProps,
          actions: (evt.payload && evt.payload.actions) || [],
          seq: evt.seq,
        };
        step.blocks.push(cardId);
        step.status = STATUS.STREAMING;
        break;
      }
      case "artifact_ready": {
        const artId = (evt.payload && evt.payload.artifact_id) || ("art_" + evt.seq);
        step.artifacts.push({
          id: artId,
          kind: (evt.payload && evt.payload.kind) || "unknown",
          ref: (evt.payload && evt.payload.ref) || null,
        });
        break;
      }
      case "step_pause":
        step.status = STATUS.AWAITING_REVIEW;
        if (evt.step_key) {
          runState.gates[evt.step_key] = {
            reason: (evt.payload && evt.payload.reason) || "需要用户确认",
            availableActions: (evt.payload && evt.payload.available_actions) || [
              { id: "approve", event: "approve_step" },
              { id: "revise", event: "revise_step" },
            ],
            openedAt: evt.ts,
          };
        }
        runState.isStreaming = false;
        break;
      case "user_patch_required":
        // SOP: 与 step_pause 配套; 此处不重复设 status
        if (evt.step_key && !runState.gates[evt.step_key]) {
          runState.gates[evt.step_key] = {
            reason: (evt.payload && evt.payload.reason) || "需要用户输入",
            availableActions: (evt.payload && evt.payload.available_actions) || [],
            openedAt: evt.ts,
          };
        }
        break;
      case "step_resumed":
        step.status = STATUS.STREAMING;
        runState.isStreaming = true;
        delete runState.gates[evt.step_key];
        break;
      case "run_completed":
        step.status = STATUS.COMPLETED;
        runState.isStreaming = false;
        break;
      case "run_failed":
        step.status = STATUS.FAILED;
        runState.isStreaming = false;
        if (evt.payload && evt.payload.error) {
          step.errorText = evt.payload.error;
        }
        break;
      default:
        // 未识别事件: 忽略, 写入 buffer 即可
        break;
    }
  }

  // ---------- Gate 操作 ----------

  function applyUserPatch(runState, stepKey, patch, actionId) {
    const step = ensureStep(runState, stepKey);
    step.userPatch = patch || step.userPatch || null;
    if (actionId === "approve") {
      step.status = STATUS.APPROVED;
      if (stepKey === "keyword_review") runState.hasApprovedGate2 = true;
      // 自动推进 currentStep 到下一个 pending
      const idx = STEP_KEYS.indexOf(stepKey);
      if (idx >= 0 && idx < STEP_KEYS.length - 1) {
        runState.currentStep = STEP_KEYS[idx + 1];
      }
    } else if (actionId === "revise") {
      step.status = STATUS.REVISING;
    }
  }

  function isStepAccessible(runState, stepKey) {
    const idx = STEP_KEYS.indexOf(stepKey);
    if (idx <= 0) return true;
    const prevKey = STEP_KEYS[idx - 1];
    const prev = runState.steps[prevKey];
    if (!prev) return false;
    return prev.status === STATUS.COMPLETED || prev.status === STATUS.APPROVED;
  }

  // ---------- 对外接口 ----------

  global.StepDeck = {
    STEP_KEYS: STEP_KEYS,
    STEP_LABELS: STEP_LABELS,
    STATUS: STATUS,
    STATUS_LABEL: STATUS_LABEL,
    EVENT_TYPES: EVENT_TYPES,
    createRunState: createRunState,
    ensureStep: ensureStep,
    makeEvent: makeEvent,
    applyEvent: applyEvent,
    applyUserPatch: applyUserPatch,
    isStepAccessible: isStepAccessible,
  };
})(window);
