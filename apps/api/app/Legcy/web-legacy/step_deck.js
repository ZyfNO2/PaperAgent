// Session 22: Step Deck UI 控制器 (SOP §4-6).
//
// - 左侧 Step Rail (9 步, 状态指示)
// - 中间主卡 (单步可见, scroll-snap)
// - 右侧 Evidence Drawer (可折叠)
// - 底部 action bar (上一步 / 下一步 / 同意 / 重新跑)
//
// Session 22: 集成 ComponentRegistry 统一渲染 6 类核心卡
// - renderKeywordCardInteractive() → ComponentRegistry.renderCard()
// - renderStepCard() → ComponentRegistry.renderCard() for step.blocks
// - renderKeywordReviewCard() → ComponentRegistry.renderCard() for step.blocks
// - renderStepCard() → ComponentRegistry.renderCard() for step.blocks
// - renderKeywordCardInteractive() → ComponentRegistry.renderCard() for keyword cards
// - renderKeywordReviewCard() → ComponentRegistry.renderCard() for keyword cards

(function (global) {
  "use strict";

  const SD = global.StepDeck;
  const RP = global.RenderProtocol;
  if (!SD) {
    console.warn("[StepDeckUI] StepDeck not loaded");
  }

  // 状态: 全局 runState 挂到 window.StepDeckUI 供测试 inspect
  const ui = {
    runState: SD ? SD.createRunState() : null,
    initialized: false,
    mockTimer: null,
  };

  // ---------- DOM helper ----------

  function el(id) { return document.getElementById(id); }

  function escapeHtml(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ---------- 渲染 Step Rail ----------

  function renderStepRail() {
    const rail = el("step-deck-rail");
    if (!rail || !ui.runState) return;
    const rs = ui.runState;
    const html = SD.STEP_KEYS.map(function (key) {
      const meta = SD.STEP_LABELS[key];
      const step = rs.steps[key] || { status: SD.STATUS.PENDING };
      const accessible = SD.isStepAccessible(rs, key);
      const isCurrent = (rs.currentStep === key);
      const cls = [
        "step-rail__item",
        "step-rail__item--" + step.status,
        isCurrent ? "is-current" : "",
        accessible ? "is-accessible" : "is-locked",
      ].filter(Boolean).join(" ");
      return '<div class="' + cls + '" data-step-key="' + key + '">' +
        '<span class="step-rail__num">' + meta.num + '</span>' +
        '<span class="step-rail__icon">' + meta.icon + '</span>' +
        '<span class="step-rail__title">' + meta.title + '</span>' +
        '<span class="step-rail__status">' + SD.STATUS_LABEL[step.status] + '</span>' +
        '</div>';
    }).join("");
    rail.innerHTML = html;
    // click handler
    rail.querySelectorAll(".step-rail__item").forEach(function (node) {
      node.addEventListener("click", function () {
        const k = node.getAttribute("data-step-key");
        if (SD.isStepAccessible(rs, k)) {
          rs.currentStep = k;
          renderAll();
        }
      });
    });
  }

  // ---------- 渲染主卡 ----------

  function renderStepCard() {
    const wrap = el("step-deck-card-wrap");
    if (!wrap || !ui.runState) return;
    const rs = ui.runState;
    const key = rs.currentStep;
    const meta = SD.STEP_LABELS[key];
    const step = rs.steps[key] || { status: SD.STATUS.PENDING, text: "", blocks: [] };

    let bodyHtml = "";
    if (key === "input") {
      // 输入题目的简易入口
      bodyHtml = renderInputCard();
    } else if (key === "keyword_review") {
      bodyHtml = renderKeywordReviewCard(step);
    } else if (step.text) {
      bodyHtml = RP ? RP.renderText(step.text) : '<p class="pa-plain">' + escapeHtml(step.text) + '</p>';
    } else {
      bodyHtml = '<p class="step-deck__placeholder">本步暂无内容. 顶部"开始流式"按钮可触发 mock 事件流, 或在经典视图 (一题分析) 中完成该步后切回此页.</p>';
    }

    // 渲染 cards (StepKey 内累积的 card_delta)
    const cardsHtml = (step.blocks || []).map(function (cid) {
      const card = rs.cards[cid];
      if (!card) return "";
      if (!RP) return '<div class="pa-card">' + escapeHtml(card.type) + '</div>';
      return RP.renderBlock(card);
    }).join("");

    wrap.innerHTML =
      '<header class="step-deck__head">' +
        '<span class="step-deck__num">' + meta.num + '</span>' +
        '<h2 class="step-deck__title">' + meta.icon + ' ' + meta.title + '</h2>' +
        '<span class="step-deck__status step-deck__status--' + step.status + '">' +
          SD.STATUS_LABEL[step.status] +
        '</span>' +
      '</header>' +
      '<div class="step-deck__body" data-step-key="' + key + '">' +
        bodyHtml +
        (cardsHtml ? '<div class="step-deck__cards">' + cardsHtml + '</div>' : "") +
      '</div>' +
      renderActionBar(key, step);
  }

  function renderInputCard() {
    return '<div class="step-deck__input">' +
      '<label class="step-deck__label">选题题目</label>' +
      '<input id="sd-input-topic" type="text" class="step-deck__text" ' +
        'value="' + escapeHtml(global.PaperAgentState && global.PaperAgentState.lastTopic || "基于YOLO的钢材表面缺陷检测") + '" />' +
      '<p class="step-deck__hint">Step 0 仅展示输入, 不会触发真分析. 请到顶部"开始流式"按钮触发 mock 流.</p>' +
      '</div>';
  }

  function renderKeywordReviewCard(step) {
    // 关键词 step 既支持 textDelta 也支持 cards
    let kwTextHtml = "";
    if (step.text) {
      kwTextHtml = RP ? RP.renderText(step.text) : '<p>' + escapeHtml(step.text) + '</p>';
    }
    // 卡片中的 KeywordReviewCard 显示为可编辑
    const cardsHtml = (step.blocks || []).map(function (cid) {
      const card = ui.runState.cards[cid];
      if (!card) return "";
      if (card.type === "KeywordReviewCard") {
        return renderKeywordCardInteractive(card);
      }
      return RP ? RP.renderBlock(card) : "";
    }).join("");
    return (kwTextHtml || "") + (cardsHtml ? '<div class="step-deck__cards">' + cardsHtml + '</div>' : "");
  }

  function renderKeywordCardInteractive(card) {
    // Session 22: 使用 ComponentRegistry 统一渲染，不再手写 HTML
    if (global.ComponentRegistry) {
      return global.ComponentRegistry.renderCard(card);
    }
    // S21 fallback (registry 未加载时保底)
    const kws = (card.props && card.props.keywords) || [];
    const editable = card.props && card.props.editable;
    return '<div class="pa-card pa-card--KeywordReviewCard' + (editable ? ' is-editable' : '') + '">' +
      '<div class="pa-card-meta">' +
        '<span class="pa-card-component">🔑 KeywordReviewCard</span>' +
        '<span class="pa-card-id">' + escapeHtml(card.id || "") + '</span>' +
      '</div>' +
      '<div class="pa-card-keywords" data-card-id="' + escapeHtml(card.id || "") + '">' +
        kws.map(function (k, i) {
          return '<span class="pa-kw" data-kind="' + escapeHtml(k.kind || "other") + '" data-idx="' + i + '">' +
            '<span class="pa-kw__text">' + escapeHtml(k.text) + '</span>' +
            (editable ? '<button class="pa-kw__del" data-action="del" data-idx="' + i + '" type="button">✕</button>' : '') +
            '</span>';
        }).join("") +
      '</div>' +
      (editable ?
        '<div class="pa-card-actions">' +
          '<button class="cta-mini" data-gate-action="approve" data-step-key="keyword_review" type="button">✅ 确认并继续</button>' +
          '<button class="cta-mini" data-gate-action="revise" data-step-key="keyword_review" type="button">✏️ 修改并继续</button>' +
        '</div>' : '') +
      '</div>';
  }

  // ---------- Action Bar ----------

  function renderActionBar(stepKey, step) {
    const rs = ui.runState;
    const idx = SD.STEP_KEYS.indexOf(stepKey);
    const hasPrev = idx > 0;
    const hasNext = idx < SD.STEP_KEYS.length - 1;
    const isGate = step.status === SD.STATUS.AWAITING_REVIEW;
    const isFailed = step.status === SD.STATUS.FAILED;
    return '<footer class="step-deck__actions">' +
      '<button class="cta-mini" id="sd-btn-prev" type="button"' + (hasPrev ? '' : ' disabled') + '>← 上一步</button>' +
      '<span class="step-deck__actions-spacer"></span>' +
      (isGate ?
        '<span class="step-deck__gate-hint">⏸ ' + escapeHtml((rs.gates[stepKey] || {}).reason || "需要确认") + '</span>' +
        '<button class="cta-mini" data-gate-action="approve" data-step-key="' + stepKey + '" type="button">✅ 通过</button>' +
        '<button class="cta-mini" data-gate-action="revise" data-step-key="' + stepKey + '" type="button">✏️ 修订</button>' : '') +
      (isFailed ?
        '<span class="step-deck__error">✗ ' + escapeHtml(step.errorText || "失败") + '</span>' : '') +
      '<button class="cta-mini" id="sd-btn-next" type="button"' + (hasNext ? '' : ' disabled') + '>下一步 →</button>' +
      '</footer>';
  }

  // ---------- Drawer ----------

  function renderDrawer() {
    const drawer = el("step-deck-drawer");
    if (!drawer) return;
    const rs = ui.runState;
    if (!rs) { drawer.innerHTML = ""; return; }
    const events = rs.eventBuffer.slice(-30);
    const evHtml = events.length
      ? events.map(function (e) {
          return '<div class="drawer__evt drawer__evt--' + e.event_type + '">' +
            '<span class="drawer__evt-seq">#' + e.seq + '</span>' +
            '<span class="drawer__evt-type">' + e.event_type + '</span>' +
            '<span class="drawer__evt-step">' + escapeHtml(e.step_key) + '</span>' +
            '</div>';
        }).join("")
      : '<p class="drawer__empty">尚无事件. 顶部"开始流式"会触发 mock 事件流.</p>';
    drawer.innerHTML =
      '<header class="drawer__head"><h3>🧠 Trace (mock)</h3></header>' +
      '<div class="drawer__list">' + evHtml + '</div>';
  }

  // ---------- 整体渲染 ----------

  function renderAll() {
    renderStepRail();
    renderStepCard();
    renderDrawer();
  }

  // ---------- 用户操作 ----------

  function onPrev() {
    const rs = ui.runState;
    const idx = SD.STEP_KEYS.indexOf(rs.currentStep);
    if (idx > 0) rs.currentStep = SD.STEP_KEYS[idx - 1];
    renderAll();
  }

  function onNext() {
    const rs = ui.runState;
    const idx = SD.STEP_KEYS.indexOf(rs.currentStep);
    if (idx < SD.STEP_KEYS.length - 1) rs.currentStep = SD.STEP_KEYS[idx + 1];
    renderAll();
  }

  function onGateAction(stepKey, actionId) {
    const rs = ui.runState;
    if (actionId === "approve") {
      // 推一个 user_patch_applied / step_resumed 风格的事件
      const resumeEvt = SD.makeEvent("step_resumed", { approved: true }, rs);
      resumeEvt.step_key = stepKey;
      SD.applyEvent(rs, resumeEvt);
      SD.applyUserPatch(rs, stepKey, { approved: true }, "approve");
      const doneEvt = SD.makeEvent("step_pause", { reason: "已通过, 推进中" }, rs);
      doneEvt.event_type = "run_completed"; // 简化: 标记当前 gate 已结束
      doneEvt.step_key = stepKey;
      SD.applyEvent(rs, doneEvt);
    } else if (actionId === "revise") {
      const evt = SD.makeEvent("user_patch_required", { reason: "用户点击修订" }, rs);
      evt.step_key = stepKey;
      SD.applyEvent(rs, evt);
      SD.applyUserPatch(rs, stepKey, { revised: true }, "revise");
    }
    renderAll();
  }

  // ---------- Mock stream ----------

  function startMockStream() {
    if (!ui.runState) return;
    const rs = ui.runState;
    rs.runId = "run_" + Date.now();
    rs.lastSeq = 0;
    rs.eventBuffer = [];
    rs.steps = {};
    rs.cards = {};
    rs.gates = {};
    rs.currentStep = "topic_understanding";

    // 事件序列: run_started -> step_started -> token_delta * 3 -> card_delta (KeywordReviewCard)
    // -> step_pause -> user_patch_required
    const seq = [
      { type: "run_started", stepKey: "topic_understanding" },
      { type: "step_started", stepKey: "topic_understanding" },
      { type: "token_delta", stepKey: "topic_understanding", payload: { text: "正在理解题目: " } },
      { type: "token_delta", stepKey: "topic_understanding", payload: { text: "基于 YOLO 的钢材表面缺陷检测." } },
      { type: "token_delta", stepKey: "topic_understanding", payload: { text: "\n\n意图: 用轻量 YOLO 在工业产线上做实时表面缺陷检测." } },
      { type: "step_started", stepKey: "keyword_review" },
      { type: "token_delta", stepKey: "keyword_review", payload: { text: "正在拆解关键词...\n" } },
      { type: "card_delta", stepKey: "keyword_review", payload: {
        id: "kw_card_1",
        component: "KeywordReviewCard",
        props: {
          keywords: [
            { kind: "method", text: "YOLO" },
            { kind: "method", text: "深度学习" },
            { kind: "task",   text: "目标检测" },
            { kind: "object", text: "钢材表面缺陷" },
            { kind: "domain", text: "工业质检" },
            { kind: "metric", text: "mAP" },
            { kind: "risk",   text: "实时" },
          ],
          editable: true,
        },
        actions: [
          { id: "approve", event: "approve_step" },
          { id: "revise", event: "revise_step" },
        ],
      } },
      { type: "step_pause", stepKey: "keyword_review", payload: {
        reason: "请审查并修改关键词, 确认后继续",
        available_actions: [
          { id: "approve", event: "approve_step" },
          { id: "revise", event: "revise_step" },
        ],
      } },
    ];

    let i = 0;
    rs.isStreaming = true;
    renderAll();

    function next() {
      if (i >= seq.length) {
        rs.isStreaming = false;
        renderAll();
        return;
      }
      const s = seq[i++];
      const evt = SD.makeEvent(s.type, s.payload || {}, rs);
      evt.step_key = s.stepKey;
      SD.applyEvent(rs, evt);
      renderAll();
      ui.mockTimer = setTimeout(next, 350);
    }
    next();
  }

  function resetDeck() {
    if (ui.mockTimer) { clearTimeout(ui.mockTimer); ui.mockTimer = null; }
    ui.runState = SD.createRunState();
    renderAll();
  }

  // ---------- 初始化 ----------

  function init() {
    if (ui.initialized) return;
    ui.initialized = true;
    if (!SD) return;
    ui.runState = SD.createRunState();
    renderAll();

    const startBtn = el("btn-sd-start-stream");
    if (startBtn) startBtn.addEventListener("click", startMockStream);
    const resetBtn = el("btn-sd-reset");
    if (resetBtn) resetBtn.addEventListener("click", resetDeck);
    const toggleBtn = el("btn-sd-toggle-drawer");
    if (toggleBtn) toggleBtn.addEventListener("click", function () {
      const d = el("step-deck-drawer");
      if (d) d.classList.toggle("is-collapsed");
    });

    // event delegation for prev / next / gate actions / del keyword
    // (prev / next buttons are recreated by renderAll, so delegate)
    const cardWrap = el("step-deck-card-wrap");
    if (cardWrap) {
      cardWrap.addEventListener("click", function (e) {
        const t = e.target;
        if (!t || !t.getAttribute) return;
        const id = t.id;
        if (id === "sd-btn-prev") { onPrev(); return; }
        if (id === "sd-btn-next") { onNext(); return; }
        const gateAction = t.getAttribute("data-gate-action");
        if (gateAction) {
          const stepKey = t.getAttribute("data-step-key");
          onGateAction(stepKey, gateAction);
          return;
        }
        const delAction = t.getAttribute("data-action");
        if (delAction === "del") {
          const idx = parseInt(t.getAttribute("data-idx"), 10);
          removeKeywordFromCard(idx);
        }
      });
    }
  }

  function removeKeywordFromCard(idx) {
    const rs = ui.runState;
    const step = rs.steps["keyword_review"];
    if (!step) return;
    const card = (step.blocks || []).map(function (cid) { return rs.cards[cid]; })
      .find(function (c) { return c && c.type === "KeywordReviewCard"; });
    if (!card || !card.props || !card.props.keywords) return;
    card.props.keywords.splice(idx, 1);
    renderAll();
  }

  // Session 23: Extended mock stream — query_plan + candidates steps.
  // Fires after keyword_review approve. Returns events (does NOT auto-fire).
  function startExtendedMockStream(rs) {
    if (!rs) return [];
    var deck = StepDeck;
    var events = [];

    // 1. keyword_review step_resumed
    var ev = deck.makeEvent("step_resumed", { reason: "user approved" }, rs);
    ev.step_key = "keyword_review";
    events.push(ev);

    // 2. query_plan step_started
    var ev2 = deck.makeEvent("step_started", {}, rs);
    ev2.step_key = "query_plan";
    events.push(ev2);

    // 3. query_plan token_delta
    var ev3 = deck.makeEvent("token_delta", { text: "正在根据关键词生成检索计划..." }, rs);
    ev3.step_key = "query_plan";
    events.push(ev3);

    // 4. query_plan card_delta — SearchQueryPlanCard
    var ev4 = deck.makeEvent("card_delta", {
      id: "card_query_plan",
      component: "SearchQueryPlanCard",
      props: {
        queries: [
          { source: "paper", query: "YOLO 钢材表面缺陷检测", priority: "high" },
          { source: "paper", query: "YOLO steel defect detection", priority: "high" },
          { source: "dataset", query: "NEU steel surface defect dataset", priority: "medium" },
          { source: "dataset", query: "钢材缺陷 数据集", priority: "medium" },
          { source: "repo", query: "ultralytics yolov8", priority: "low" },
          { source: "repo", query: "yolo defect detection github", priority: "low" },
        ],
      },
      actions: ["approve_step", "revise_step"],
    }, rs);
    ev4.step_key = "query_plan";
    events.push(ev4);

    // 5. query_plan step_pause
    var ev5 = deck.makeEvent("step_pause", {
      reason: "检索计划待确认",
      available_actions: [
        { id: "approve", event: "approve_step" },
        { id: "revise", event: "revise_step" },
      ],
    }, rs);
    ev5.step_key = "query_plan";
    events.push(ev5);

    return events;
  }

  // Session 23: Candidates mock stream — fired after query_plan approve.
  function startCandidatesMockStream(rs) {
    if (!rs) return [];
    var deck = StepDeck;
    var events = [];

    // 1. query_plan step_resumed
    var ev1 = deck.makeEvent("step_resumed", { reason: "user approved query_plan" }, rs);
    ev1.step_key = "query_plan";
    events.push(ev1);

    // 2. candidates step_started
    var ev2 = deck.makeEvent("step_started", {}, rs);
    ev2.step_key = "candidates";
    events.push(ev2);

    // 3. candidates token_delta
    var ev3 = deck.makeEvent("token_delta", { text: "正在检索候选资源..." }, rs);
    ev3.step_key = "candidates";
    events.push(ev3);

    // 4. RetrievalCandidateCard (paper)
    var ev4 = deck.makeEvent("card_delta", {
      id: "card_cand_001",
      component: "RetrievalCandidateCard",
      props: {
        kind: "paper",
        title: "Steel Surface Defect Detection Using Improved YOLOv5",
        url: "https://example.com/paper1",
        source: "IEEE Access",
        confidence: "high",
        matched_keywords: ["YOLO", "钢材表面缺陷", "目标检测"],
      },
      actions: ["save_candidate", "reject_candidate", "open_drawer"],
    }, rs);
    ev4.step_key = "candidates";
    events.push(ev4);

    // 5. RetrievalCandidateCard (dataset)
    var ev5 = deck.makeEvent("card_delta", {
      id: "card_cand_002",
      component: "RetrievalCandidateCard",
      props: {
        kind: "dataset",
        title: "NEU Steel Surface Defect Database",
        url: "https://example.com/dataset1",
        source: "Kaggle",
        confidence: "medium",
        matched_keywords: ["钢材表面缺陷", "工业质检"],
      },
      actions: ["save_candidate", "reject_candidate", "open_drawer"],
    }, rs);
    ev5.step_key = "candidates";
    events.push(ev5);

    // 6. RetrievalCandidateCard (repo)
    var ev6 = deck.makeEvent("card_delta", {
      id: "card_cand_003",
      component: "RetrievalCandidateCard",
      props: {
        kind: "repo",
        title: "ultralytics/ultralytics",
        url: "https://github.com/ultralytics/ultralytics",
        source: "GitHub",
        confidence: "high",
        matched_keywords: ["YOLO", "ultralytics"],
      },
      actions: ["save_candidate", "reject_candidate", "open_drawer"],
    }, rs);
    ev6.step_key = "candidates";
    events.push(ev6);

    // 7. candidates step_pause
    var ev7 = deck.makeEvent("step_pause", {
      reason: "候选资源待审查",
      available_actions: [
        { id: "approve", event: "approve_step" },
        { id: "revise", event: "revise_step" },
      ],
    }, rs);
    ev7.step_key = "candidates";
    events.push(ev7);

    return events;
  }

  // ---------- 对外接口 ----------

  global.StepDeckUI = {
    ui: ui,
    init: init,
    renderAll: renderAll,
    startMockStream: startMockStream,
    startExtendedMockStream: startExtendedMockStream,
    startCandidatesMockStream: startCandidatesMockStream,
    resetDeck: resetDeck,
    onPrev: onPrev,
    onNext: onNext,
    onGateAction: onGateAction,
    isReady: function () { return ui.initialized; },
  };
})(window);
