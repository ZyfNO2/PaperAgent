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

function ratingBadge(r) {
  return { A: "🟢 A", B: "🔵 B", C: "🟡 C", D: "🔴 D" }[r] || r || "-";
}

// Phase 04: 论文 / 数据集 / Baseline 卡片
function _renderEvidenceCards(ledger) {
  if (!ledger) return "";
  const papers = ledger.papers || [];
  const datasets = ledger.datasets || [];
  const baselines = ledger.baselines || [];

  const sourceBadge = (s) => {
    const map = {
      "arXiv": '<span class="badge badge--arxiv">arXiv</span>',
      "user-uploaded": '<span class="badge badge--uploaded">我加的</span>',
      "LLM-generated-candidate": '<span class="badge badge--llm">LLM 占位</span>',
    };
    return map[s] || `<span class="badge badge--other">${s}</span>`;
  };

  const paperCards = papers.map(p => {
    const kw = (p.keywords_zh || []).slice(0, 5);
    const field = p.field ? `<span class="badge badge--field">📂 ${p.field}</span>` : "";
    const zhSum = p.summary_zh ? `
      <div class="evidence-card__zh-summary">
        <span class="zh-label">中文</span>${p.summary_zh}
      </div>
    ` : "";
    const kwChips = kw.length ? `
      <div class="evidence-card__keywords">
        ${kw.map(k => `<span class="kw-chip">${k}</span>`).join("")}
      </div>
    ` : "";
    return `
    <div class="evidence-card" data-source="${p.source}">
      <div class="evidence-card__head">
        <div class="evidence-card__title">${(p.title || "").slice(0, 90)}${(p.title || "").length > 90 ? "..." : ""}</div>
        ${sourceBadge(p.source)}
      </div>
      <div class="evidence-card__meta">
        ${p.year ? `[${p.year}]` : ""}
        ${(p.authors || []).length ? " · 作者: " + p.authors.slice(0, 3).join(", ") + (p.authors.length > 3 ? ` +${p.authors.length - 3}` : "") : ""}
      </div>
      ${field || kwChips || zhSum ? `<div class="evidence-card__zh-row">${field}${kwChips}</div>` : ""}
      ${zhSum}
      ${p.abstract ? `<details class="evidence-card__abstract"><summary>📄 英文原文摘要</summary><div>${(p.abstract || "").slice(0, 500)}${(p.abstract || "").length > 500 ? "..." : ""}</div></details>` : ""}
      <div class="evidence-card__links">
        ${p.url ? `<a href="${p.url}" target="_blank" rel="noopener" class="btn-link">📄 arXiv 页面</a>` : ""}
        ${p.url ? `<a href="${p.url.replace('/abs/', '/pdf/')}.pdf" target="_blank" rel="noopener" class="btn-link">⬇️ PDF</a>` : ""}
      </div>
    </div>
  `}).join("");

  const datasetCards = datasets.map(d => `
    <div class="evidence-card evidence-card--small">
      <div class="evidence-card__head">
        <div class="evidence-card__title">${d.name || d.dataset_id}</div>
        <span class="badge badge--fit-${d.fit_to_topic === "高" ? "high" : d.fit_to_topic === "中" ? "mid" : "low"}">契合度 ${d.fit_to_topic || "中"}</span>
      </div>
      <div class="evidence-card__meta">规模: ${d.scale || "未知"} · 许可: ${d.license || "未知"}</div>
      ${d.download ? `<a href="${d.download}" target="_blank" rel="noopener" class="btn-link">⬇️ 下载</a>` : ""}
    </div>
  `).join("");

  const baselineCards = baselines.map(b => `
    <div class="evidence-card evidence-card--small">
      <div class="evidence-card__head">
        <div class="evidence-card__title">${b.name || b.baseline_id}</div>
        <span class="badge badge--diff-${b.reproduce_difficulty}">复现 ${b.reproduce_difficulty || "中"}</span>
      </div>
      <div class="evidence-card__meta">${b.paper_title || ""}</div>
      ${b.repository_url ? `<a href="${b.repository_url}" target="_blank" rel="noopener" class="btn-link">🔗 仓库</a>` : ""}
    </div>
  `).join("");

  return `
    <div class="phase-section-title">📚 论文卡片 (${papers.length})</div>
    <div class="evidence-card-list">${paperCards || '<div class="empty-hint">暂无论文</div>'}</div>
    <div class="phase-section-title">💾 数据集 (${datasets.length})</div>
    <div class="evidence-card-list">${datasetCards || '<div class="empty-hint">暂无数据集</div>'}</div>
    <div class="phase-section-title">⚙️ Baseline (${baselines.length})</div>
    <div class="evidence-card-list">${baselineCards || '<div class="empty-hint">暂无 baseline</div>'}</div>
  `;
}

// Phase 04: 用户手动添加论文表单
function _renderAddPaperForm() {
  return `
    <details class="add-paper-form">
      <summary>➕ 添加我自己的论文 (师兄师姐 / 导师推荐)</summary>
      <div class="add-paper-form__body">
        <div class="form-row">
          <label>标题 (必填) <input name="title" placeholder="如: LightGCN: Simplifying..."></label>
        </div>
        <div class="form-row">
          <label>作者 (逗号分隔) <input name="authors" placeholder="He, X., Deng, K., Wang, X., Li, Y."></label>
          <label>年份 <input name="year" type="number" placeholder="2020"></label>
        </div>
        <div class="form-row">
          <label>URL (arXiv 或 DOI) <input name="url" placeholder="https://arxiv.org/abs/2002.02126"></label>
        </div>
        <div class="form-row">
          <label>摘要 (选填) <textarea name="abstract" rows="3" placeholder="一句话讲清方法/结果"></textarea></label>
        </div>
        <div class="form-row form-row--actions">
          <button class="cta-primary" id="btn-add-paper">📥 添加</button>
          <span class="form-hint">添加后立即出现在论文卡片列表</span>
        </div>
      </div>
    </details>
  `;
}

// Phase 03: 7 层检索词展开
function _renderSearchPlan(plan) {
  if (!plan || !plan.query_layers) return "";
  const layers = plan.query_layers || [];
  if (!layers.length) return "";
  return `
    <details class="risk-signals" open>
      <summary>🔍 7 层检索词 (每层前 2 条)</summary>
      <div class="risk-signals__body">
        ${layers.map(l => `
          <div class="risk-signal">
            <div class="risk-signal__head">
              <span class="risk-signal__name">${l.layer} · ${l.title}</span>
              <span class="risk-signal__score">${(l.queries || []).length} 个</span>
            </div>
            <div class="risk-signal__summary">${l.purpose || ""}</div>
            <div class="risk-signal__pluses">
              ${(l.queries || []).slice(0, 2).map(q =>
                `<div class="signal-line signal-line--plus">▸ ${q}</div>`
              ).join("")}
            </div>
          </div>
        `).join("")}
      </div>
    </details>
  `;
}

// Phase 05: 6 维 ++ / -- 评分信号
function _renderRiskSignals(risk) {
  if (!risk) return "";
  const dims = risk.dimensions || (risk.risk_score && risk.risk_score.dimensions) || [];
  if (!dims.length) return "";
  const rs = risk.risk_score || risk;
  return `
    <details class="risk-signals" open>
      <summary>📊 评分信号 (6 维 ++ / -- 明细)</summary>
      <div class="risk-signals__body">
        <div class="risk-signals__overall">
          总分 <strong>${(rs.overall_score || 0).toFixed(1)}</strong> / 评级
          <strong>${rs.overall_rating || "?"}</strong> · 最弱维度: ${rs.max_risk_dimension || "—"}
        </div>
        ${dims.map(d => `
          <div class="risk-signal">
            <div class="risk-signal__head">
              <span class="risk-signal__name">${d.key}</span>
              <span class="risk-signal__score">${(d.score || 0).toFixed(1)} / 100</span>
            </div>
            <div class="risk-signal__summary">${d.evidence_summary || ""}</div>
            ${(d.pluses && d.pluses.length) ? `
              <div class="risk-signal__pluses">
                ${d.pluses.map(p => `<div class="signal-line signal-line--plus">++ ${p}</div>`).join("")}
              </div>
            ` : ""}
            ${(d.minuses && d.minuses.length) ? `
              <div class="risk-signal__minuses">
                ${d.minuses.map(m => `<div class="signal-line signal-line--minus">-- ${m}</div>`).join("")}
              </div>
            ` : ""}
          </div>
        `).join("")}
      </div>
    </details>
  `;
}

function renderResult(n, data) {
  let rows = [];
  let extra = "";
  if (n === 1) {
    // Phase 01: 评级 + 字段齐备度公式
    const intake = state.intake?.payload || {};
    rows = [
      ["case_id", data.case_id || "-"],
      ["intake_rating", ratingBadge(data.rating)],
      ["目标档位", data.goal_level || intake.goal_level || "-"],
      ["学位", intake.degree_type || "-"],
      ["导师方向", data.advisor_direction || intake.advisor_direction || "-"],
      ["开题时间", intake.proposal_deadline || "-"],
      ["毕业时间", intake.thesis_deadline || "-"],
      ["首张结果表", intake.first_result_deadline || "-"],
      ["缺失字段", (intake.missing_fields?.length || 0) + " 项"],
      ["allow_proceed", data.rating === "A" || data.rating === "B" ? "✓ 是" : "✗ 否"],
    ];
    const rating = data.rating || "?";
    const reason =
      rating === "A" ? "✓ 全部补齐, 无缺失字段"
        : rating === "B" ? `有 P1 / P2 缺失 (${intake.missing_fields?.length || 0} 项, 优先级 P1/P2)`
          : rating === "C" ? "有 P0 缺失 (必填字段未填)"
            : "占位符 (TBD/TODO) 或 P0≥4 ∩ P1≥2 (严重缺失)";
    extra = `
      <div class="phase-formula">
        <div class="phase-formula__title">📐 评分公式: A + B + C → rating</div>
        <div class="phase-formula__body">
          <code>intake_rating = f(missing_fields, 字段齐备度, 占位检测)</code><br>
          <span class="formula-tag">A</span> = 全部补齐, 无缺失<br>
          <span class="formula-tag formula-tag--b">B</span> = 有 P1/P2 缺失 (一般字段)<br>
          <span class="formula-tag formula-tag--c">C</span> = 有 P0 缺失 (必填字段)<br>
          <span class="formula-tag formula-tag--d">D</span> = 占位符 (TBD/TODO) 或 P0≥4 且 P1≥2<br>
          <hr style="margin:8px 0; border-color:#fcd34d;">
          <strong>本项目:</strong> rating = <span class="formula-tag">${rating}</span>
          = ${reason}
        </div>
      </div>
      ${intake.missing_fields?.length ? `
        <div class="phase-missing">
          <div class="phase-missing__title">⚠️ 缺失字段明细 (${intake.missing_fields.length} 项)</div>
          <ul>${intake.missing_fields.slice(0, 5).map(m => `<li><strong>${m.field_name}</strong>: ${m.why_required || ""} ${m.priority ? `<code>[${m.priority}]</code>` : ""}</li>`).join("")}</ul>
        </div>
      ` : `<div class="phase-tip">✓ 无缺失字段, 可以放心进入 Phase 02</div>`}
    `;
  } else if (n === 2) {
    // Phase 02: 9 拆解字段 + 风险词 → rating 公式
    const spec = state.topicSpec || {};
    const risks = spec.risk_terms || [];
    const riskCount = risks.length;
    rows = [
      ["normalized_topic", (spec.normalized_topic || data.normalized_topic || "-").slice(0, 30) + ((spec.normalized_topic || data.normalized_topic || "").length > 30 ? "..." : "")],
      ["research_object", spec.research_object || data.research_object || "-"],
      ["task_count", (spec.task_type || data.task_type || []).length],
      ["method_count", (spec.method_family || data.method_family || []).length],
      ["data_count", (spec.data_requirement || []).length],
      ["metric_count", (spec.evaluation_metrics || []).length],
      ["risk_terms", riskCount + " 个"],
      ["decomposition_rating", ratingBadge(spec.decomposition_rating || data.decomposition_rating)],
      ["allow_proceed", String(data.allow_proceed_to_phase03 ?? spec.allow_proceed_to_phase03)],
    ];
    const rating = spec.decomposition_rating || data.decomposition_rating || "?";
    const ratingReason =
      riskCount >= 8 ? `${riskCount} ≥ 8 风险词 → C`
        : riskCount >= 4 ? `${riskCount} ∈ [4, 7] 风险词 → B`
          : `${riskCount} ∈ [0, 3] 风险词 → A`;
    extra = `
      <div class="phase-formula">
        <div class="phase-formula__title">📐 评分公式: risks_count + allow_proceed → rating</div>
        <div class="phase-formula__body">
          <code>decomposition_rating = f(risks_count) ∧ allow_proceed_to_phase03</code><br>
          <span class="formula-tag">A</span> = 0-3 风险词, 且 WP≥2 + 章节齐 + 评价指标非空<br>
          <span class="formula-tag formula-tag--b">B</span> = 4-7 风险词<br>
          <span class="formula-tag formula-tag--c">C</span> = 8+ 风险词 (智能/高精度/端到端 等 12 个模糊词)<br>
          <span class="formula-tag formula-tag--d">D</span> = 阻断 (WP 缺 / 章节缺 / 评价空)<br>
          <hr style="margin:8px 0; border-color:#fcd34d;">
          <strong>本项目:</strong> rating = <span class="formula-tag">${rating}</span>
          = ${ratingReason}
        </div>
      </div>
      <details class="phase-detail" open>
        <summary>📋 9 拆解字段明细 (点击折叠)</summary>
        <ul>
          <li><strong>研究对象</strong>: ${spec.research_object || data.research_object || "-"}</li>
          <li><strong>应用场景</strong>: ${spec.application_scenario || data.application_scenario || "-"}</li>
          <li><strong>任务类型</strong>: ${(spec.task_type || data.task_type || []).join("、") || "-"}</li>
          <li><strong>数据模态</strong>: ${(spec.data_modality || data.data_modality || []).join("、") || "-"}</li>
          <li><strong>方法族</strong>: ${(spec.method_family || data.method_family || []).join("、") || "-"}</li>
          <li><strong>预期输出</strong>: ${(spec.expected_outputs || data.expected_outputs || []).join("、") || "-"}</li>
          <li><strong>评价指标</strong>: ${(spec.evaluation_metrics || data.evaluation_metrics || []).join("、") || "-"}</li>
          <li><strong>工程约束</strong>: ${(spec.engineering_constraints || data.engineering_constraints || []).join("、") || "-"}</li>
          <li><strong>风险词</strong>: ${risks.length ? risks.map(r => `<code>${r.term || r}</code>`).join("、") : "✓ 无"}</li>
        </ul>
      </details>
    `;
  }
  else if (n === 3) {
    rows = [
      ["maturity_rating", data.maturity_rating || "-"],
      ["layer_count", data.layer_count || "-"],
      ["query_total", data.query_total || "-"],
      ["allow_proceed", String(data.allow_proceed_to_phase04)],
    ];
    // 7 层检索词展开
    extra = _renderSearchPlan(state.searchPlan);
  }
  else if (n === 4) {
    rows = [
      ["evidence_rating", data.evidence_rating],
      ["paper_count", data.paper_count],
      ["arxiv_papers", data.arxiv_papers || 0],
      ["datasets", data.dataset_count],
      ["baselines", data.baseline_count],
    ];
    // 论文卡片区: 从 state.evidenceLedger 读 papers / datasets / baselines
    extra = _renderEvidenceCards(state.evidenceLedger) + _renderAddPaperForm();
  }
  else if (n === 5) {
    rows = [
      ["rating", data.overall_rating],
      ["score", data.overall_score?.toFixed(1)],
      ["decision", data.decision],
      ["pivots", data.pivot_count],
    ];
    // 评分信号: 6 维 ++ / -- 明细
    extra = _renderRiskSignals(state.riskEvaluation);
  }
  else if (n === 6) rows = [
    ["final_topic", (data.final_topic || "").slice(0, 30) + "..."],
    ["from_pivot", String(data.from_pivot)],
    ["WPs", data.work_package_count],
    ["experiments", data.experiment_count],
  ];
  else if (n === 7) {
    // Phase 07: 合并 proposal_meta + committee_meta
    const p = data.proposal || {};
    const c = data.committee || {};
    rows = [
      ["proposal_sections", p.section_count ?? p.proposal_sections ?? "—"],
      ["innovation_count", p.innovation_count ?? "—"],
      ["verdict", c.overall_verdict || "—"],
      ["maturity", c.proposal_maturity || "—"],
      ["discussion", c.discussion_count || 0],
    ];
    // 委员会 3 角色对话气泡
    if (c.discussion && c.discussion.length) {
      extra = `<div class="phase-section-title">🎙️ 委员会 3 角色对话</div>` +
        c.discussion.map(d => `
          <div class="discussion-bubble ${d.role}">
            <div class="role ${d.role}">${d.role === 'supporter' ? '支持' : d.role === 'skeptic' ? '质疑' : '折中'}</div>
            <div class="body">${(d.comment || "").slice(0, 280)}${(d.comment || "").length > 280 ? "..." : ""}</div>
          </div>
        `).join("");
    }
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
    ${extra}
  `;
}

function renderPhase01Form() {
  return `
    <form class="phase-card__form" id="form-phase-01">
      <div class="phase-card__row">
        <label>案例编号 (case_id) <input name="case_id" value="YOLO_THESIS" required></label>
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
      <label>导师方向 <input name="advisor_direction" value="工业质检"></label>
      <label>原始题目 <textarea name="raw_topic" required>基于轻量化注意力机制的YOLOv8带钢表面缺陷检测算法研究</textarea></label>
      <div class="phase-card__row">
        <label>必须保留 <input name="must_keep" value="YOLOv8, 带钢表面缺陷, 轻量化, 注意力机制"></label>
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
      // 把 missing_fields 塞回 intake.payload (vj.missing_fields 是 validate 返回的)
      if (vj.missing_fields) {
        data.payload.missing_fields = vj.missing_fields;
      }
      state.intake = data;
      state.phases[1].done = true;
      state.phases[1].data = {
        case_id: vj.case_id, rating: vj.intake_rating,
        goal_level: intake.goal_level, advisor_direction: intake.advisor_direction,
        missing_fields: vj.missing_fields || [],
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
      // 拿完整 spec (result meta 不全, 用 GET 拉)
      try {
        const resp = await fetch(API + `/api/v1/projects/${state.projectId}/topic/spec`);
        if (resp.ok) {
          const full = await resp.json();
          state.topicSpec = full.payload || full;
          state.phases[2].data = state.topicSpec;
        } else {
          state.topicSpec = r;
        }
      } catch {
        state.topicSpec = r;
      }
      renderStepper();
      renderCurrentPanel();
    }
  },
  async runPhase3() {
    const r = await runStream(`/api/v1/projects/${state.projectId}/search/plan/stream`);
    if (r) {
      state.phases[3].done = true;
      state.phases[3].data = r;
      // 拉完整 search plan (含每层 query 列表) 供 _renderSearchPlan 展示
      try {
        const resp = await fetch(API + `/api/v1/projects/${state.projectId}/search/plan`);
        if (resp.ok) {
          const full = await resp.json();
          state.searchPlan = full.payload || full;
        }
      } catch (_) { /* */ }
      renderStepper();
      renderCurrentPanel();
    }
  },
  async runPhase4() {
    // prefer=auto: 让 LLM 出真实摘要 (summary_zh/keywords_zh/field); 失败 fallback heuristic
    const r = await runStream(`/api/v1/projects/${state.projectId}/evidence/build/stream`, { prefer: "auto" });
    if (r) {
      state.phases[4].done = true;
      state.phases[4].data = r;
      // 拉完整 evidence ledger (含 papers / datasets / baselines 详情) 供论文卡片渲染
      try {
        const resp = await fetch(API + `/api/v1/projects/${state.projectId}/evidence/ledger`);
        if (resp.ok) {
          const full = await resp.json();
          state.evidenceLedger = full.payload || full;
        }
      } catch (_) { /* 保留空 */ }
      renderStepper();
      renderCurrentPanel();
    }
  },
  async runPhase5() {
    const r = await runStream(`/api/v1/projects/${state.projectId}/risk/evaluate/stream`, { prefer: "heuristic" });
    if (r) {
      state.phases[5].done = true;
      state.phases[5].data = r;
      // 拉完整 risk evaluation (含 dimensions[].pluses/minuses)
      try {
        const resp = await fetch(API + `/api/v1/projects/${state.projectId}/risk/evaluation`);
        if (resp.ok) {
          const full = await resp.json();
          state.riskEvaluation = full.payload || full;
        }
      } catch (_) { /* 保留空 */ }
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
      // proposal 完成后 step-dot 7 标 done (committee 是 secondary, 不阻塞 7 的 done 态)
      state.phases[7].done = true;
      // 拉完整 proposal (含 sections 详情) 备用
      try {
        const resp = await fetch(API + `/api/v1/projects/${state.projectId}/proposal/draft`);
        if (resp.ok) {
          const full = await resp.json();
          state.proposalDraft = full.payload || full;
        }
      } catch (_) { /* */ }
      renderStepper();
      renderCurrentPanel();
    }
  },
  async runPhase7b() {
    const r = await runStream(`/api/v1/projects/${state.projectId}/committee/review/stream`);
    if (r) {
      state.phases[7].data = state.phases[7].data || {};
      state.phases[7].data.committee = r;
      // 拉完整 committee review (含 3 角色 discussion 列表) 渲染对话气泡
      try {
        const resp = await fetch(API + `/api/v1/projects/${state.projectId}/committee/review`);
        if (resp.ok) {
          const full = await resp.json();
          state.committeeReview = full.payload || full;
          // 把 discussion 列表也写到 phases[7].data.committee 让卡片直接读
          state.phases[7].data.committee.discussion = (state.committeeReview.discussion || []).map(d => ({
            role: d.role, stance: d.stance, comment: d.comment,
          }));
        }
      } catch (_) { /* */ }
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

// 全局: 监听 add-paper 按钮点击 (Phase 04 渲染时挂上)
document.addEventListener("click", async (e) => {
  if (e.target && e.target.id === "btn-add-paper") {
    e.preventDefault();
    const form = e.target.closest(".add-paper-form");
    if (!form) return;
    const get = (name) => form.querySelector(`[name="${name}"]`)?.value || "";
    const body = {
      title: get("title").trim(),
      authors: get("authors").trim(),
      year: parseInt(get("year")) || null,
      url: get("url").trim() || null,
      abstract: get("abstract").trim() || null,
    };
    if (!body.title) {
      alert("请填标题");
      return;
    }
    appendTrace({ type: "step", name: "addPaper", detail: `提交: ${body.title.slice(0, 30)}` });
    try {
      const r = await fetch(API + `/api/v1/projects/${state.projectId}/papers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (r.status === 200 || r.status === 201) {
        const data = await r.json();
        appendTrace({ type: "result", name: "论文添加成功", detail: `papers=${data.paper_count}` });
        state.evidenceLedger = data.payload;
        state.phases[4].data = data;
        renderCurrentPanel();
      } else {
        const t = await r.text();
        appendTrace({ type: "error", name: "添加失败", detail: t.slice(0, 200) });
        alert("添加失败: " + t.slice(0, 200));
      }
    } catch (err) {
      appendTrace({ type: "error", name: "添加异常", detail: String(err).slice(0, 200) });
    }
  }
});
renderCurrentPanel();
