// TopicPilot-CN v2: 一页一动作 + 流式 Agent trace
// 状态机: currentPhase 1-8; 每完成一步切下一个 phase, 同时保留历史可回看
// 流式: fetch + ReadableStream 调 /api/v1/projects/{id}/<phase>/<action>/stream

const API = "http://127.0.0.1:18181";

const state = {
  projectId: null,
  currentPhase: 1,                  // 1-8 当前显示的 phase
  phases: {                         // 每 phase 状态
    1: { done: false, data: null },
    2: { done: false, data: null },
    3: { done: false, data: null },
    4: { done: false, data: null },
    5: { done: false, data: null },
    6: { done: false, data: null },
    7: { done: false, data: { proposal: null, committee: null } },
    8: { done: false, data: null },
  },
  trace: [],                        // 流式 trace 事件累积
  streamAbort: null,                // 当前流式 fetch 的 AbortController
  blocked: false,                   // Phase 01 阻断
};

// ---------- 8 phase 路由表 ----------

const PHASE_DEFS = {
  1: {
    icon: "📝",
    eyebrow: "Step 01 · 任务建档",
    title: "填好研究背景, 系统会给你 A/B/C/D 评级",
    desc: "专业 / 目标档位 / 时间 / 原始题目 缺一不可. D 评级会阻断后续 6 个 phase.",
    renderForm: renderPhase01Form,
    primary: { label: "创建项目 + 自动评级", action: "createProject" },
  },
  2: {
    icon: "🔍",
    eyebrow: "Step 02 · 题目拆解",
    title: "把自然语言题目拆成结构化 TopicSpec",
    desc: "识别研究对象 / 任务 / 模态 / 方法 / 数据 / 评价. 同时扫 8 个高风险词 (智能 / 高精度 / 端到端...).",
    primary: { label: "开始拆解", action: "runPhase2" },
  },
  3: {
    icon: "🗺️",
    eyebrow: "Step 03 · 检索计划",
    title: "7 层 × 121 个检索词覆盖研究现状",
    desc: "L0 精确 → L1 中英同义 → L2 去场景 → L3 抽象任务 → L4 基线 → L5 综述 → L6 中文.",
    primary: { label: "生成检索计划", action: "runPhase3" },
  },
  4: {
    icon: "📚",
    eyebrow: "Step 04 · 证据账本",
    title: "真 arXiv 检索 + 论文 / 数据 / Baseline",
    desc: "调 arXiv 公开 API 拉真实论文. 启发式时用占位论文, LLM 路径会按 arXiv 真实结果扩.",
    primary: { label: "生成证据账本 (含 arXiv 真检索)", action: "runPhase4" },
  },
  5: {
    icon: "⚖️",
    eyebrow: "Step 05 · 风险评分",
    title: "6 维评分 + M3 生成 Pivot 候选",
    desc: "文献 / 数据 / Baseline / 评价 / 资源 / 范围 / 工作包. 决策: 继续 / 收缩 / 转向 / 停止.",
    primary: { label: "评估风险", action: "runPhase5" },
  },
  6: {
    icon: "📦",
    eyebrow: "Step 06 · 工作包",
    title: "把题目拆成 2-3 个可验证工作包",
    desc: "每 WP 含独立研究问题 / 数据 / 对照 / 评价 / 论文章节. 失败不串行.",
    primary: { label: "定稿工作包", action: "runPhase6" },
  },
  7: {
    icon: "📄",
    eyebrow: "Step 07 · 开题报告 + 委员会",
    title: "10 节报告 + 7 维审查 + 3 角色 LLM 对话",
    desc: "Supporter / Skeptic / Pragmatist 三个 '教授' 给出开题版评语 (不学术答辩腔).",
    primary: { label: "生成开题报告", action: "runPhase7a" },
    secondary: { label: "再走委员会审查", action: "runPhase7b" },
  },
  8: {
    icon: "🎓",
    eyebrow: "Step 08 · 最终材料",
    title: "Markdown 初稿 + 3 维验收 + 浏览器下载",
    desc: "包含 10 节 + 创新点 + 答辩问答 + 风险预案 + 7 维审查 + 9 个未来工作.",
    primary: { label: "组装最终材料", action: "runPhase8" },
    secondary: { label: "导出 Markdown 到本地", action: "exportMarkdown" },
  },
};

// ============================================================ 渲染
// ============================================================

function renderStepper() {
  document.querySelectorAll(".step-dot").forEach(dot => {
    const n = parseInt(dot.dataset.phase, 10);
    dot.classList.remove("step-dot--active", "step-dot--done");
    dot.disabled = !state.phases[n].done && n !== state.currentPhase && !canReach(n);
    if (state.phases[n].done) dot.classList.add("step-dot--done");
    if (n === state.currentPhase) dot.classList.add("step-dot--active");
  });
}

function canReach(n) {
  if (n === 1) return true;
  return state.phases[n - 1].done;
}

function renderCurrentPanel() {
  const def = PHASE_DEFS[state.currentPhase];
  const panel = document.getElementById("phase-panel");
  const pState = state.phases[state.currentPhase];
  const formHtml = def.renderForm ? def.renderForm() : "";
  const resultHtml = pState.data ? renderResult(state.currentPhase, pState.data) : "";
  const isFirstActive = state.currentPhase === 1 && !pState.data;

  panel.innerHTML = `
    <div class="phase-card">
      <div class="phase-card__icon">${def.icon}</div>
      <div class="phase-card__eyebrow">${def.eyebrow}</div>
      <h2 class="phase-card__title">${def.title}</h2>
      <p class="phase-card__desc">${def.desc}</p>
      ${isFirstActive ? formHtml : ""}
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <button class="cta-primary" id="btn-primary" ${pState.done ? "disabled" : ""}>
          ${pState.done ? "✓ 已完成" : def.primary.label}
        </button>
        ${def.secondary && !pState.done
          ? `<button class="cta-ghost" id="btn-secondary">${def.secondary.label}</button>`
          : ""}
        ${pState.done && state.currentPhase < 8
          ? `<button class="cta-ghost" id="btn-next">下一步 →</button>`
          : ""}
        ${state.currentPhase > 1
          ? `<button class="cta-ghost" id="btn-prev">← 上一步</button>`
          : ""}
      </div>
      ${resultHtml}
    </div>
  `;

  const btn = document.getElementById("btn-primary");
  if (btn && !pState.done) btn.addEventListener("click", () => runAction(def.primary.action));
  const sec = document.getElementById("btn-secondary");
  if (sec) sec.addEventListener("click", () => runAction(def.secondary.action));
  const nxt = document.getElementById("btn-next");
  if (nxt) nxt.addEventListener("click", () => goToPhase(state.currentPhase + 1));
  const prv = document.getElementById("btn-prev");
  if (prv) prv.addEventListener("click", () => goToPhase(state.currentPhase - 1));
}

function renderResult(n, data) {
  let rows = [];
  if (n === 1) rows = [
    ["case_id", data.case_id], ["rating", data.rating],
    ["目标档位", data.goal_level], ["导师", data.advisor_direction],
  ];
  else if (n === 2) rows = [
    ["normalized_topic", (data.normalized_topic || "").slice(0, 24) + "..."],
    ["task_count", (data.task_type || []).length],
    ["decomposition_rating", data.decomposition_rating || "-"],
    ["allow_proceed", String(data.allow_proceed_to_phase03)],
  ];
  else if (n === 3) rows = [
    ["maturity_rating", data.maturity_rating || "-"],
    ["layer_count", data.layer_count || "-"],
    ["query_total", data.query_total || "-"],
    ["allow_proceed", String(data.allow_proceed_to_phase04)],
  ];
  else if (n === 4) rows = [
    ["evidence_rating", data.evidence_rating],
    ["paper_count", data.paper_count],
    ["arxiv_papers", data.arxiv_papers || 0],
    ["datasets", data.dataset_count],
    ["baselines", data.baseline_count],
  ];
  else if (n === 5) rows = [
    ["rating", data.overall_rating],
    ["score", data.overall_score?.toFixed(1)],
    ["decision", data.decision],
    ["pivots", data.pivot_count],
  ];
  else if (n === 6) rows = [
    ["final_topic", (data.final_topic || "").slice(0, 30) + "..."],
    ["from_pivot", String(data.from_pivot)],
    ["WPs", data.work_package_count],
    ["experiments", data.experiment_count],
  ];
  else if (n === 7) {
    const c = data.committee || {};
    rows = [
      ["proposal_sections", data.proposal_sections],
      ["innovation_count", data.innovation_count],
      ["verdict", c.overall_verdict || "—"],
      ["maturity", c.proposal_maturity || "—"],
      ["discussion", c.discussion_count || 0],
    ];
  } else if (n === 8) rows = [
    ["ready_for_thesis", String(data.ready_for_thesis)],
    ["backend", data.backend_verification],
    ["ui", data.ui_verification],
    ["playwright", data.playwright_verification],
    ["markdown", data.proposal_markdown_chars + " chars"],
  ];
  return `
    <div class="phase-result">
      <div class="phase-result__head">✓ Phase ${String(n).padStart(2, "0")} 产物</div>
      <div class="phase-result__grid">
        ${rows.map(([k, v]) => `<div class="phase-result__row">
          <span class="phase-result__k">${k}</span>
          <span class="phase-result__v">${v}</span>
        </div>`).join("")}
      </div>
    </div>
  `;
}

function renderPhase01Form() {
  return `
    <form class="phase-card__form" id="form-phase-01">
      <div class="phase-card__row">
        <label>案例编号 (case_id) <input name="case_id" value="WEB_V2" required></label>
        <label>专业 <input name="major" value="计算机科学与技术"></label>
        <label>学位 <select name="degree_type">
          <option>本科</option><option selected>硕士</option><option>博士</option>
        </select></label>
        <label>目标档位 <select name="goal_level">
          <option selected>保毕业</option><option>稳中求新</option><option>冲高水平</option>
        </select></label>
      </div>
      <div class="phase-card__row">
        <label>开题时间 <input name="proposal_deadline" value="2026-10-15"></label>
        <label>毕业时间 <input name="thesis_deadline" value="2027-06-01"></label>
        <label>首张结果表 <input name="first_result_deadline" value="2026-12-31"></label>
      </div>
      <label>导师方向 <input name="advisor_direction" value="图神经网络"></label>
      <label>原始题目 <textarea name="raw_topic" required>基于图神经网络的学术论文推荐方法研究</textarea></label>
      <div class="phase-card__row">
        <label>必须保留 <input name="must_keep" value="图神经网络, 推荐"></label>
        <label>每周投入 (h) <input name="weekly_hours" type="number" value="25" min="0" max="168"></label>
      </div>
    </form>
  `;
}

// ============================================================ 流式
// ============================================================

function appendTrace(ev) {
  state.trace.push(ev);
  renderTraceList();
}

function renderTraceList() {
  const list = document.getElementById("trace-list");
  const count = document.getElementById("trace-count");
  count.textContent = state.trace.length;
  if (state.trace.length === 0) {
    list.innerHTML = '<div class="trace-empty">尚无 trace 事件</div>';
    return;
  }
  list.innerHTML = state.trace.slice(-100).map(ev => {
    const icon = ({
      start: "🚀", step: "🔹", llm: "🤖",
      warn: "⚠️", result: "✅", error: "❌",
    })[ev.type] || "·";
    const meta = ev.meta && Object.keys(ev.meta).length
      ? `<div class="trace-item__meta">${Object.entries(ev.meta).slice(0, 3).map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v).slice(0, 40) : v}`).join('  ')}</div>`
      : "";
    return `<div class="trace-item trace-item--${ev.type}">
      <div class="trace-item__icon">${icon}</div>
      <div class="trace-item__body">
        <div class="trace-item__name">${ev.name || ev.type}</div>
        <div class="trace-item__detail">${ev.detail || ""}</div>
        ${meta}
      </div>
      <div class="trace-item__time">${ev.ts_ms ? new Date(ev.ts_ms).toLocaleTimeString('zh-CN', { hour12: false }).slice(0, 8) : ""}</div>
    </div>`;
  }).join("");
  list.scrollTop = list.scrollHeight;
}

async function runStream(endpoint, body) {
  // 清空当前 trace 面板
  state.trace = [];
  renderTraceList();
  document.getElementById("trace-sub").textContent =
    `正在调 ${endpoint.replace("/stream", "")} (流式)...`;

  if (state.streamAbort) state.streamAbort.abort();
  state.streamAbort = new AbortController();

  const r = await fetch(API + endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
    signal: state.streamAbort.signal,
  });
  if (!r.ok) {
    const err = await r.text();
    appendTrace({ type: "error", name: "HTTP " + r.status, detail: err.slice(0, 200) });
    throw new Error(`HTTP ${r.status}`);
  }
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let result = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n\n");
    buf = lines.pop();
    for (const chunk of lines) {
      if (!chunk.startsWith("data: ")) continue;
      try {
        const ev = JSON.parse(chunk.slice(6));
        appendTrace(ev);
        if (ev.type === "result") {
          result = ev.meta || {};
        }
      } catch (e) { /* ignore */ }
    }
  }
  return result;
}

// ============================================================ Action
// ============================================================

function runAction(name) {
  if (!state.projectId && name !== "createProject") {
    alert("请先完成 Phase 01 建档");
    return;
  }
  handlers[name]();
}

const handlers = {
  async createProject() {
    const fd = new FormData(document.getElementById("form-phase-01"));
    const intake = {
      case_id: fd.get("case_id") + "_" + Date.now().toString().slice(-6),
      major: fd.get("major"), degree_type: fd.get("degree_type"),
      goal_level: fd.get("goal_level"),
      thesis_deadline: fd.get("thesis_deadline"),
      proposal_deadline: fd.get("proposal_deadline"),
      first_result_deadline: fd.get("first_result_deadline"),
      advisor_direction: fd.get("advisor_direction"),
      school_requirements: [], inherited_resources: [],
      student_resources: {
        programming_level: "熟练", dl_or_algorithm_foundation: "中",
        paper_reading_ability: "中", english_reading_ability: "中",
        compute_resource: "笔记本 3060", weekly_hours: parseInt(fd.get("weekly_hours")) || 25,
        data_collection_ability: "中", data_annotation_ability: "中",
        code_reproduction_ability: "中", system_dev_ability: "中",
      },
      raw_topic: fd.get("raw_topic"),
      must_keep: (fd.get("must_keep") || "").split(",").map(s => s.trim()).filter(Boolean),
      can_drop: [], missing_fields: [], intake_rating: "A",
    };
    appendTrace({ type: "start", name: "createProject", detail: "提交 Phase 01 建档" });
    try {
      const r = await fetch(API + "/api/v1/projects", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intake }),
      });
      if (r.status !== 201) {
        const t = await r.text();
        appendTrace({ type: "error", name: "HTTP " + r.status, detail: t.slice(0, 200) });
        return;
      }
      const data = await r.json();
      state.projectId = data.id;
      appendTrace({ type: "step", name: "validate", detail: "调 intake/validate 走评级判定" });
      const v = await fetch(API + `/api/v1/projects/${state.projectId}/intake/validate`, { method: "POST" });
      const vj = await v.json();
      if (vj.outcome !== "OK") {
        state.blocked = true;
        appendTrace({ type: "warn", name: "BLOCKED", detail: `outcome=${vj.outcome} rating=${vj.intake_rating}` });
        return;
      }
      state.phases[1].done = true;
      state.phases[1].data = {
        case_id: vj.case_id, rating: vj.intake_rating,
        goal_level: intake.goal_level, advisor_direction: intake.advisor_direction,
      };
      appendTrace({ type: "result", name: "Phase 01 完成", detail: `case_id=${vj.case_id} rating=${vj.intake_rating}` });
      renderStepper();
      renderCurrentPanel();
    } catch (e) {
      appendTrace({ type: "error", name: "createProject", detail: String(e).slice(0, 200) });
    }
  },

  async runPhase2() {
    const r = await runStream(`/api/v1/projects/${state.projectId}/topic/decompose/stream`, { prefer: "heuristic" });
    if (r) {
      state.phases[2].done = true;
      state.phases[2].data = r;
      renderStepper();
      renderCurrentPanel();
    }
  },
  async runPhase3() {
    const r = await runStream(`/api/v1/projects/${state.projectId}/search/plan/stream`);
    if (r) {
      state.phases[3].done = true;
      state.phases[3].data = r;
      renderStepper();
      renderCurrentPanel();
    }
  },
  async runPhase4() {
    const r = await runStream(`/api/v1/projects/${state.projectId}/evidence/build/stream`, { prefer: "heuristic" });
    if (r) {
      state.phases[4].done = true;
      state.phases[4].data = r;
      renderStepper();
      renderCurrentPanel();
    }
  },
  async runPhase5() {
    const r = await runStream(`/api/v1/projects/${state.projectId}/risk/evaluate/stream`, { prefer: "heuristic" });
    if (r) {
      state.phases[5].done = true;
      state.phases[5].data = r;
      renderStepper();
      renderCurrentPanel();
    }
  },
  async runPhase6() {
    const r = await runStream(`/api/v1/projects/${state.projectId}/work_package/plan/stream`);
    if (r) {
      state.phases[6].done = true;
      state.phases[6].data = r;
      renderStepper();
      renderCurrentPanel();
    }
  },
  async runPhase7a() {
    const r = await runStream(`/api/v1/projects/${state.projectId}/proposal/draft/stream`);
    if (r) {
      state.phases[7].data = state.phases[7].data || {};
      state.phases[7].data.proposal = r;
      renderStepper();
      renderCurrentPanel();
    }
  },
  async runPhase7b() {
    const r = await runStream(`/api/v1/projects/${state.projectId}/committee/review/stream`);
    if (r) {
      state.phases[7].data = state.phases[7].data || {};
      state.phases[7].data.committee = r;
      state.phases[7].done = true;
      renderStepper();
      renderCurrentPanel();
    }
  },
  async runPhase8() {
    const r = await runStream(`/api/v1/projects/${state.projectId}/final_package/build/stream`);
    if (r) {
      state.phases[8].done = true;
      state.phases[8].data = r;
      renderStepper();
      renderCurrentPanel();
    }
  },
  async exportMarkdown() {
    const r = await fetch(API + `/api/v1/projects/${state.projectId}/final_package/markdown`);
    if (r.status === 200) {
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `proposal_${state.projectId}.md`;
      a.click();
      URL.revokeObjectURL(url);
      appendTrace({ type: "result", name: "export", detail: "已下载 proposal_" + state.projectId + ".md" });
    } else {
      appendTrace({ type: "error", name: "export", detail: "HTTP " + r.status });
    }
  },
};

function goToPhase(n) {
  if (n < 1 || n > 8) return;
  if (!canReach(n) && n > state.currentPhase) {
    appendTrace({ type: "warn", name: "blocked", detail: `Phase ${n} 未到, 完成上一步后才能看` });
    return;
  }
  state.currentPhase = n;
  renderStepper();
  renderCurrentPanel();
}

// ============================================================ Init
// ============================================================

document.querySelectorAll(".step-dot").forEach(dot => {
  dot.addEventListener("click", () => {
    const n = parseInt(dot.dataset.phase, 10);
    goToPhase(n);
  });
});

document.getElementById("btn-trace-clear").addEventListener("click", () => {
  state.trace = [];
  renderTraceList();
});

document.getElementById("api-base").textContent = API;
renderStepper();
renderCurrentPanel();
