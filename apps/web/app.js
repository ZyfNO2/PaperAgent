// TopicPilot-CN OneTopic MVP — 极简前端
// 流程: 输入题目 → 调 POST /analyze/stream → 边推 trace 边渲 5 区结果
// 扩展: Session 2 加证据工作台 + tab 切换 + 手动添加/审核

const API = "http://127.0.0.1:18181";

const state = {
  result: null,
  projectId: "",
  trace: [],
  streamAbort: null,
  running: false,
  currentTab: "analyze", // "analyze" | "evidence"
};

// ---------- Trace ----------

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
      start: "🚀", step: "🔹", warn: "⚠️", result: "✅", error: "❌",
    })[ev.type] || "·";
    return `<div class="trace-item trace-item--${ev.type}">
      <div class="trace-item__icon">${icon}</div>
      <div class="trace-item__body">
        <div class="trace-item__detail">${escapeHtml(ev.detail || "")}</div>
        <div class="trace-item__name">${escapeHtml(ev.name || ev.type)}</div>
      </div>
    </div>`;
  }).join("");
  list.scrollTop = list.scrollHeight;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// ---------- Session 7: EvidenceRef 渲染 + 复核动作 (§8) ----------

function renderEvidenceRefs(refs, opts) {
  // refs: list of EvidenceRef. opts: { target_type, target_id }.
  // Returns HTML string of small ref cards with remove / mark_core buttons.
  opts = opts || {};
  if (!refs || refs.length === 0) {
    return '<div class="ref-empty">⚠ 无证据引用</div>';
  }
  return refs.map(r => `
    <div class="ref-card ref-card--${escapeHtml(r.role)}" data-ref-id="${escapeHtml(r.evidence_id)}">
      <div class="ref-card__head">
        <span class="ref-card__role ref-card__role--${escapeHtml(r.role)}">${escapeHtml(r.role)}</span>
        <span class="ref-card__type">${escapeHtml(r.evidence_type)}</span>
        <span class="ref-card__status">${escapeHtml(r.review_status)}</span>
        ${r.score != null ? `<span class="ref-card__score">${r.score.toFixed(2)}</span>` : ""}
      </div>
      <div class="ref-card__title">${escapeHtml(r.title)}</div>
      <div class="ref-card__reason">${escapeHtml(r.reason || "")}</div>
      <div class="ref-card__actions">
        ${r.url ? `<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener" class="ref-link">🔗 打开</a>` : ""}
        ${opts.target_type ? `
          <button class="ref-btn" data-ref-action="mark_ref_core" data-evidence-id="${escapeHtml(r.evidence_id)}" type="button">⭐ 标核心</button>
          <button class="ref-btn" data-ref-action="mark_ref_wrong" data-evidence-id="${escapeHtml(r.evidence_id)}" type="button">❌ 标错</button>
          <button class="ref-btn" data-ref-action="remove_ref" data-evidence-id="${escapeHtml(r.evidence_id)}" type="button">🗑 移除</button>
        ` : ""}
      </div>
    </div>
  `).join("");
}

async function reviewRef(projectId, targetType, targetId, evidenceId, action, reason) {
  const body = {
    target_type: targetType,
    target_id: targetId,
    evidence_id: evidenceId,
    action: action,
    reason: reason || null,
  };
  const r = await fetch(`${API}/api/v1/one-topic/${projectId}/evidence/refs/review`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    appendTrace({ type: "warn", name: "ref-review-failed", detail: `HTTP ${r.status}` });
    return null;
  }
  const data = await r.json();
  appendTrace({
    type: "step", name: `ref-${action}`,
    detail: `${targetType}/${targetId} ${evidenceId}: ${data.new_coverage_score.toFixed(2)}`,
  });
  return data;
}

async function refreshRefs(projectId) {
  // Re-fetch coverage; state.result snapshot is server-side already updated.
  try {
    const r = await fetch(`${API}/api/v1/one-topic/${projectId}/evidence/refs/coverage`);
    if (!r.ok) return null;
    return await r.json();
  } catch (e) {
    return null;
  }
}

// ---------- Tab 切换 ----------

function switchTab(name) {
  state.currentTab = name;
  document.querySelectorAll(".tab").forEach(t => {
    t.classList.toggle("tab--active", t.dataset.tab === name);
  });
  document.getElementById("page-analyze").hidden = (name !== "analyze");
  document.getElementById("page-evidence").hidden = (name !== "evidence");
  if (name === "evidence" && state.projectId) {
    refreshEvidence();
  }
}

// ---------- SSE 流 ----------

async function runStream(endpoint, body) {
  if (state.streamAbort) state.streamAbort.abort();
  state.streamAbort = new AbortController();
  state.trace = [];
  renderTraceList();
  document.getElementById("trace-sub").textContent =
    `正在调 ${endpoint.replace("/stream", "")} (流式)...`;

  const r = await fetch(API + endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
    signal: state.streamAbort.signal,
  });
  if (!r.ok) {
    const err = await r.text();
    appendTrace({ type: "error", name: "HTTP " + r.status, detail: err.slice(0, 300) });
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
        if (ev.type === "result" && ev.meta) {
          result = ev.meta;
        }
      } catch (e) { /* ignore */ }
    }
  }
  return result;
}

// ---------- 结果渲染 (analyze page) ----------

function renderResult(r) {
  document.getElementById("result-grid").hidden = false;

  // Session 7 §8.3: 覆盖率低时显示 banner
  const feas = r.feasibility || {};
  const rec = r.proposal_recommendation || {};
  const totalRefs = (feas.evidence_refs ? feas.evidence_refs.length : 0)
    + (rec.topic_evidence_refs ? rec.topic_evidence_refs.length : 0)
    + rec.pivot_routes.reduce((s, p) => s + (p.evidence_refs ? p.evidence_refs.length : 0), 0)
    + rec.work_packages.reduce((s, w) => s + (w.evidence_refs ? w.evidence_refs.length : 0), 0)
    + (r.light_review ? r.light_review.checks.reduce((s, c) => s + (c.evidence_refs ? c.evidence_refs.length : 0), 0) : 0);
  const banner = document.getElementById("coverage-banner");
  if (banner) {
    banner.hidden = false;
    banner.className = "coverage-banner coverage-banner--ok";
    banner.innerHTML = `🔗 共挂载 <strong>${totalRefs}</strong> 条证据引用 (feasibility ${feas.evidence_refs ? feas.evidence_refs.length : 0} · pivot ${rec.pivot_routes.filter(p => p.evidence_refs && p.evidence_refs.length).length}/${rec.pivot_routes.length} · WP ${rec.work_packages.filter(w => w.evidence_refs && w.evidence_refs.length).length}/${rec.work_packages.length})`;
  }

  // Block 1: 题目理解
  const tu = r.topic_understanding || {};
  document.getElementById("block-understanding").innerHTML = `
    <div class="topic-understanding__intent">${escapeHtml(tu.intent_zh || "")}</div>
    <div class="topic-understanding__meta">
      <span>原始: <code>${escapeHtml(tu.raw_topic || "")}</code></span>
      <span>标准化: <code>${escapeHtml(tu.normalized_topic || "")}</code></span>
      <span>具体对象: <code>${tu.is_specific_object ? "✓ 是" : "✗ 否"}</code></span>
    </div>
  `;

  // Block 2: 关键词拆解
  const kb = r.keyword_breakdown || {};
  const kwChips = (arr, cls = "") => (arr || []).length
    ? arr.map(x => `<span class="kw-chip ${cls}">${escapeHtml(x)}</span>`).join("")
    : '<span class="evidence-empty">无</span>';
  document.getElementById("block-keywords").innerHTML = `
    <div class="kw-header">
      <span style="color:#8b94a8;font-size:12px;">点击下方词条右上角✏️ 可编辑</span>
      <button class="cta-mini" id="btn-edit-keywords" type="button">✏️ 编辑关键词</button>
    </div>
  ` + `
    <div class="kw-group">
      <div class="kw-group__label">🔧 方法词 (${(kb.method_keywords || []).length})</div>
      <div class="kw-group__chips">${kwChips(kb.method_keywords)}</div>
    </div>
    <div class="kw-group">
      <div class="kw-group__label">📋 任务词 (${(kb.task_keywords || []).length})</div>
      <div class="kw-group__chips">${kwChips(kb.task_keywords)}</div>
    </div>
    <div class="kw-group">
      <div class="kw-group__label">🎯 对象词 (${(kb.object_keywords || []).length})</div>
      <div class="kw-group__chips">${kwChips(kb.object_keywords)}</div>
    </div>
    <div class="kw-group">
      <div class="kw-group__label">🌐 场景词 (${(kb.scenario_keywords || []).length})</div>
      <div class="kw-group__chips">${kwChips(kb.scenario_keywords)}</div>
    </div>
    <div class="kw-group">
      <div class="kw-group__label">📏 指标词 (${(kb.metric_keywords || []).length})</div>
      <div class="kw-group__chips">${kwChips(kb.metric_keywords)}</div>
    </div>
    <div class="kw-group">
      <div class="kw-group__label">⚠️ 风险词 (${(kb.risk_terms || []).length})</div>
      <div class="kw-group__chips">${kwChips(kb.risk_terms, "kw-chip--risk")}</div>
    </div>
  `;

  // Block 3: 证据 (原版, 详细卡片在 evidence page)
  // Session 5: 展示 score / type (§7.1)
  const ev = r.evidence_summary || {};
  // 评分色阶 class
  const relCls = (s) => s == null ? "" : (s >= 0.6 ? "evidence-card__score--rel--high" : (s < 0.3 ? "evidence-card__score--rel--low" : "evidence-card__score--rel"));
  const paperCards = (ev.papers || []).map(p => `
    <div class="evidence-card">
      <div class="evidence-card__title">${escapeHtml((p.title || "").slice(0, 100))}
        <span class="evidence-card__source evidence-card__source--${p.source}">${p.source}</span>
      </div>
      <div class="evidence-card__meta">${p.year ? `[${p.year}]` : ""}${(p.authors && p.authors.length) ? " · " + escapeHtml(p.authors.slice(0, 3).join(", ")) : ""}</div>
      <div class="evidence-card__scores">
        <span class="evidence-card__score ${relCls(p.relevance_score)}">相关性: ${p.relevance_score != null ? p.relevance_score.toFixed(2) : "-"}</span>
        ${p.paper_type ? `<span class="evidence-card__type evidence-card__type--${p.paper_type}">${p.paper_type}</span>` : ""}
      </div>
      ${p.url ? `<a href="${escapeHtml(p.url)}" target="_blank" rel="noopener">📄 arXiv</a>` : ""}
    </div>
  `).join("") || '<div class="evidence-empty">暂无论文</div>';
  const datasetCards = (ev.datasets || []).map(d => `
    <div class="evidence-card">
      <div class="evidence-card__title">${escapeHtml(d.name || d.dataset_id)}
        <span class="evidence-card__source evidence-card__source--${d.source}">${d.source}</span>
      </div>
      <div class="evidence-card__meta">规模: ${escapeHtml(d.scale || "未知")} · 契合度: ${escapeHtml(d.fit || "中")}</div>
      <div class="evidence-card__scores">
        <span class="evidence-card__score ${relCls(d.quality_score)}">可用性: ${d.quality_score != null ? d.quality_score.toFixed(2) : "-"}</span>
        ${d.dataset_status ? `<span class="evidence-card__type evidence-card__type--${d.dataset_status}">${d.dataset_status}</span>` : ""}
      </div>
      ${d.download ? `<a href="${escapeHtml(d.download)}" target="_blank" rel="noopener">⬇️ 下载</a>` : ""}
    </div>
  `).join("") || '<div class="evidence-empty">暂无数据集</div>';
  const baselineCards = (ev.baselines || []).map(b => `
    <div class="evidence-card">
      <div class="evidence-card__title">${escapeHtml(b.name || b.baseline_id)}
        <span class="evidence-card__source evidence-card__source--${b.source}">${b.source}</span>
      </div>
      <div class="evidence-card__meta">复现难度: ${escapeHtml(b.reproduce_difficulty || "中")}</div>
      <div class="evidence-card__scores">
        <span class="evidence-card__score ${relCls(b.quality_score)}">可复现: ${b.quality_score != null ? b.quality_score.toFixed(2) : "-"}</span>
        ${b.repo_type ? `<span class="evidence-card__type evidence-card__type--${b.repo_type}">${b.repo_type}</span>` : ""}
      </div>
      ${b.repository_url ? `<a href="${escapeHtml(b.repository_url)}" target="_blank" rel="noopener">🔗 仓库</a>` : ""}
    </div>
  `).join("") || '<div class="evidence-empty">暂无 baseline</div>';

  document.getElementById("block-evidence").innerHTML = `
    <div class="evidence-section__toolbar">
      <button class="evidence-section__btn-rescore" id="btn-rescore" type="button" data-project-id="${escapeHtml(r.project_id || "")}">🔄 重新评分证据</button>
      <span class="evidence-section__sort">
        排序:
        <select id="sort-papers">
          <option value="score-desc">按评分↓</option>
          <option value="score-asc">按评分↑</option>
          <option value="year-desc">按年份↓</option>
          <option value="year-asc">按年份↑</option>
        </select>
      </span>
    </div>
    <div class="evidence-section">
      <div class="evidence-section__title">📚 论文 <span class="evidence-section__count">${ev.paper_count || 0}</span> (arXiv 真实 ${ev.arxiv_paper_count || 0})</div>
      <div class="evidence-list" data-evidence-list="papers">${paperCards}</div>
    </div>
    <div class="evidence-section">
      <div class="evidence-section__title">💾 数据集 <span class="evidence-section__count">${ev.dataset_count || 0}</span></div>
      <div class="evidence-list" data-evidence-list="datasets">${datasetCards}</div>
    </div>
    <div class="evidence-section">
      <div class="evidence-section__title">⚙️ Baseline <span class="evidence-section__count">${ev.baseline_count || 0}</span></div>
      <div class="evidence-list" data-evidence-list="baselines">${baselineCards}</div>
    </div>
    <div class="evidence-section">
      <div class="evidence-section__title">📏 评价指标: ${(ev.metrics || []).map(escapeHtml).join("、") || "无"}</div>
    </div>
    <p style="margin-top:8px;font-size:12px;color:#8b94a8;">
      切换到 "证据工作台" tab 可手动加论文 / 接受 / 拒绝 / 删除
    </p>
    <button class="cta-mini" id="btn-edit-search-plan" type="button" style="margin-top:8px;">✏️ 编辑检索词</button>
  `;

  // Block 4: 可行性 (feas 已在 renderResult 顶部声明)
  const feasRefsHtml = renderEvidenceRefs(feas.evidence_refs || [], { target_type: "feasibility", target_id: "main" });
  const feasBlockingHtml = (feas.blocking_refs && feas.blocking_refs.length)
    ? `<div class="feasibility__blocking">
         <div class="feasibility__blocking-title">🚫 阻断依据</div>
         ${renderEvidenceRefs(feas.blocking_refs, { target_type: "feasibility", target_id: "main" })}
       </div>` : "";
  const feasMissingHtml = (feas.missing_ref_reasons && feas.missing_ref_reasons.length)
    ? `<div class="feasibility__missing-refs">
         <div class="feasibility__missing-refs-title">⚠ 证据缺口</div>
         <ul>${feas.missing_ref_reasons.map(x => `<li>${escapeHtml(x)}</li>`).join("")}</ul>
       </div>` : "";
  document.getElementById("block-feasibility").innerHTML = `
    <div class="feasibility__verdict feasibility__verdict--${escapeHtml(feas.verdict || "暂缓")}">${escapeHtml(feas.verdict || "暂缓")}</div>
    <div class="feasibility__reason">${escapeHtml(feas.reason || "")}</div>
    <div class="feasibility__confidence">证据覆盖置信度: <strong>${(feas.confidence || 0).toFixed(2)}</strong></div>
    <div class="feasibility__status">
      <div class="feasibility__status-item">论文: ${escapeHtml(feas.paper_status || "")}</div>
      <div class="feasibility__status-item">数据集: ${escapeHtml(feas.dataset_status || "")}</div>
      <div class="feasibility__status-item">Baseline: ${escapeHtml(feas.baseline_status || "")}</div>
      <div class="feasibility__status-item">工程: ${escapeHtml(feas.engineering_status || "")}</div>
    </div>
    ${(feas.missing_evidence || []).length ? `
      <div class="feasibility__missing">
        <div class="feasibility__missing-title">⚠️ 缺失证据</div>
        <ul>${feas.missing_evidence.map(x => `<li>${escapeHtml(x)}</li>`).join("")}</ul>
      </div>
    ` : ""}
    <details class="ref-panel" open>
      <summary>🔗 结论引用 (${(feas.evidence_refs || []).length} 条)</summary>
      ${feasRefsHtml}
      ${feasBlockingHtml}
      ${feasMissingHtml}
    </details>
    <div class="feasibility__next">${escapeHtml(feas.recommended_next_action || "")}</div>
    ${(feas.verdict === "可转向" || feas.verdict === "收缩后可做") ? `
      <div style="margin-top:10px;">
        <button class="cta-mini" id="btn-show-pivots" type="button">🔀 看 3 条退化路线</button>
      </div>
    ` : ""}
  `;

  // Block 5: 开题建议 + 审核 (rec 已在 renderResult 顶部声明)
  const rev = r.light_review || {};
  const wpHtml = (rec.work_packages || []).map(wp => {
    const wpRefsHtml = renderEvidenceRefs(wp.evidence_refs || [], { target_type: "work_package", target_id: wp.wp_id });
    const wpOpenQsHtml = (wp.open_questions && wp.open_questions.length)
      ? `<details class="wp-card__open-q"><summary>⚠ 待补 (${wp.open_questions.length})</summary><ul>${wp.open_questions.map(q => `<li>${escapeHtml(q)}</li>`).join("")}</ul></details>` : "";
    const statusBadge = wp.status === "needs_evidence"
      ? `<span class="wp-card__status wp-card__status--needs">待补证据</span>` : "";
    return `
    <div class="wp-card" data-wp-id="${escapeHtml(wp.wp_id)}">
      <div class="wp-card__id">${escapeHtml(wp.wp_id)} · ${escapeHtml(wp.chapter || "")} ${statusBadge}</div>
      <div class="wp-card__title">${escapeHtml(wp.title || "")}</div>
      <div class="wp-card__detail"><strong>问题:</strong> ${escapeHtml(wp.research_question || "")}</div>
      <div class="wp-card__detail"><strong>方法:</strong> ${escapeHtml(wp.method_approach || "")}</div>
      <div class="wp-card__detail"><strong>数据:</strong> ${escapeHtml(wp.data_source || "")}</div>
      <div class="wp-card__detail"><strong>实验:</strong> ${escapeHtml(wp.experiment_plan || "")}</div>
      <details class="wp-card__refs"><summary>🔗 引用 (${(wp.evidence_refs || []).length})</summary>${wpRefsHtml}</details>
      ${wpOpenQsHtml}
    </div>
  `;
  }).join("");
  const checksHtml = (rev.checks || []).map(c => {
    const checkRefsHtml = renderEvidenceRefs(c.evidence_refs || [], { target_type: "review_check", target_id: c.dimension });
    return `
    <div class="review__check" data-check-dim="${escapeHtml(c.dimension)}">
      <div class="review__check-dim">${escapeHtml(c.dimension)} <span class="review__check-conf">conf=${(c.confidence || 0).toFixed(2)}</span></div>
      <div class="review__check-result review__check-result--${escapeHtml(c.result)}">${escapeHtml(c.result)}</div>
      <div class="review__check-comment">${escapeHtml(c.comment || "")}</div>
      <details class="review__check-refs"><summary>🔗 引用 (${(c.evidence_refs || []).length})</summary>${checkRefsHtml}</details>
    </div>
  `;
  }).join("");
  const checklistHtml = (rev.revision_checklist || []).map(x => `<li>${escapeHtml(x)}</li>`).join("");
  document.getElementById("block-recommendation").innerHTML = `
    <div class="proposal__topic">📌 ${escapeHtml(rec.recommended_topic || "")}</div>
    ${(rec.topic_evidence_refs && rec.topic_evidence_refs.length) ? `
      <details class="proposal__topic-refs" open>
        <summary>🔗 题目引用 (${rec.topic_evidence_refs.length})</summary>
        ${renderEvidenceRefs(rec.topic_evidence_refs, {})}
      </details>
    ` : ""}
    <div class="proposal__reason">
      推荐理由:
      <ul>${(rec.recommendation_reason || []).map((x, i) => {
        const reason_key = `reason_${i+1}`;
        const refs = (rec.reason_evidence_refs || {})[reason_key] || [];
        return `<li>${escapeHtml(x)}${refs.length ? ` <span class="reason-refs-count">[${refs.length} 引用]</span>` : ` <span class="reason-no-refs">[待补证据]</span>`}</li>`;
      }).join("")}</ul>
    </div>
    <div class="wp-list">${wpHtml}</div>
    <details class="outline-list">
      <summary>📋 开题结构 (8 节)</summary>
      <ol>${(rec.proposal_outline || []).map(x => `<li>${escapeHtml(x)}</li>`).join("")}</ol>
    </details>
    ${(rec.pivot_routes || []).length > 0 ? `
      <details class="outline-list" open>
        <summary>🔀 退化路线 (${rec.pivot_routes.length} 条)</summary>
        <div style="font-size:11px;color:#8b94a8;margin-top:6px;">选一条 → 系统生成对应工作包</div>
        ${rec.pivot_routes.map(r => `
          <div class="pivot-card" style="margin-top:8px;">
            <div class="pivot-card__head">
              <span class="pivot-card__level pivot-card__level--${r.level}">${r.level}</span>
              <div class="pivot-card__title">${escapeHtml(r.new_topic)}</div>
            </div>
            <div class="pivot-card__tradeoff">${escapeHtml(r.tradeoff)}</div>
            <div class="pivot-card__keywords">
              ${(r.preserved_keywords || []).map(k => `<span class="pivot-card__kw">✓ ${escapeHtml(k)}</span>`).join("")}
              ${(r.removed_keywords || []).map(k => `<span class="pivot-card__kw pivot-card__kw--removed">✗ ${escapeHtml(k)}</span>`).join("")}
            </div>
            <div class="pivot-card__select">
              <button class="cta-mini" data-action="select-pivot" data-level="${r.level}" data-new-topic="${escapeHtml(r.new_topic)}" type="button">✓ 选这条路</button>
            </div>
          </div>
        `).join("")}
      </details>
    ` : ""}
    <div class="review__verdict review__verdict--${escapeHtml(rev.verdict || "需修改")}">🛡️ ${escapeHtml(rev.verdict || "需修改")}</div>
    <div class="review__summary">${escapeHtml(rev.summary || "")}</div>
    <div class="review__checks">${checksHtml}</div>
    <div class="review__checklist-title">📝 修改清单</div>
    <ol class="review__checklist">${checklistHtml}</ol>

    ${renderReportBlock(state.projectId)}
  `;
}

// ---------- Session 8: FinalPackage 报告区 ---------- //

function renderReportBlock(projectId) {
  // 占位: report block 已经在 index.html 里写好, 这里只负责 populate 数据
  // 实际 fetch + 填充由 buildReport / refreshReportSummary 完成
  if (!projectId) {
    return `<div class="report__hint">先跑一次分析, 再生成开题报告</div>`;
  }
  return "";  // 数据通过 refreshReportSummary 填充
}

async function buildReport() {
  if (!state.projectId) {
    showError("先跑一次分析");
    return;
  }
  const btn = document.getElementById("btn-build-report");
  if (btn) btn.disabled = true;
  appendTrace({ type: "step", name: "build-report", detail: "生成开题报告" });
  try {
    const r = await fetch(`${API}/api/v1/one-topic/${state.projectId}/final-package/build`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!r.ok) {
      showError("生成报告失败: " + (await r.text()).slice(0, 200));
      return;
    }
    const pkg = await r.json();
    state.finalPackage = pkg;
    renderReportSummary(pkg);
    showReportPreview(pkg.proposal_markdown);
    appendTrace({ type: "step", name: "report-built", detail: `共 ${pkg.proposal_markdown_chars} 字, ${pkg.citation_count} 引用` });
  } catch (e) {
    showError("生成报告异常: " + String(e).slice(0, 200));
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function refreshReportSummary() {
  if (!state.projectId) return;
  try {
    const r = await fetch(`${API}/api/v1/one-topic/${state.projectId}/final-package`);
    if (r.status === 409) return;  // 还没 build
    if (!r.ok) return;
    const summary = await r.json();
    renderReportSummary(summary);
  } catch (_) {
    /* silent */
  }
}

function renderReportSummary(pkg) {
  const summary = document.getElementById("report-summary");
  const readyVal = document.getElementById("report-ready-val");
  const covVal = document.getElementById("report-coverage-val");
  const charsVal = document.getElementById("report-chars-val");
  const sectionsVal = document.getElementById("report-sections-val");
  const citationsVal = document.getElementById("report-citations-val");
  const warnChip = document.getElementById("report-warning-chip");
  const btnBuild = document.getElementById("btn-build-report");
  const btnRebuild = document.getElementById("btn-rebuild-report");
  const btnDownload = document.getElementById("btn-download-report");
  const btnPreview = document.getElementById("btn-preview-report");

  if (summary) summary.hidden = false;
  if (readyVal) readyVal.textContent = pkg.ready_for_proposal ? "可提交草稿" : "需补证据";
  if (covVal) covVal.textContent = (pkg.coverage_score ?? 0).toFixed(2);
  if (charsVal) charsVal.textContent = pkg.proposal_markdown_chars ?? "-";
  if (sectionsVal) sectionsVal.textContent = pkg.section_count ?? "-";
  if (citationsVal) citationsVal.textContent = pkg.citation_count ?? "-";
  if (warnChip) warnChip.hidden = !pkg.low_coverage_warning;

  if (btnBuild) btnBuild.hidden = true;
  if (btnRebuild) btnRebuild.hidden = false;
  if (btnDownload) btnDownload.hidden = false;
  if (btnPreview) btnPreview.hidden = false;
}

function showReportPreview(md) {
  const pre = document.getElementById("report-preview");
  if (pre) {
    pre.textContent = md || "";
    pre.hidden = false;
  }
}

function toggleReportPreview() {
  const pre = document.getElementById("report-preview");
  if (pre) pre.hidden = !pre.hidden;
}

function downloadReport() {
  if (!state.projectId) return;
  const url = `${API}/api/v1/one-topic/${state.projectId}/final-package/markdown`;
  // 浏览器直接下载
  window.open(url, "_blank");
  appendTrace({ type: "step", name: "download-report", detail: "下载 Markdown" });
}


// ---------- 证据工作台 (Session 2) ----------

const REVIEW_LABELS = {
  pending: "待审",
  accepted: "接受",
  core: "核心",
  background: "背景",
  rejected: "拒绝",
  needs_check: "待核",
};

function renderEvidence(ledger) {
  // summary cells
  document.getElementById("sum-paper").textContent = ledger.paper_count || 0;
  document.getElementById("sum-dataset").textContent = ledger.dataset_count || 0;
  document.getElementById("sum-repo").textContent = ledger.repo_count || 0;
  document.getElementById("sum-accepted").textContent = ledger.accepted_count || 0;
  document.getElementById("sum-core").textContent = ledger.core_count || 0;
  document.getElementById("sum-rejected").textContent = ledger.rejected_count || 0;

  // tab badge
  const badge = document.getElementById("tab-evidence-count");
  const total = (ledger.paper_count || 0) + (ledger.dataset_count || 0) + (ledger.repo_count || 0);
  if (total > 0) {
    badge.textContent = total;
    badge.hidden = false;
  } else {
    badge.hidden = true;
  }

  // lists
  renderEvList("ev-paper-list", ledger.papers || [], "paper");
  renderEvList("ev-dataset-list", ledger.datasets || [], "dataset");
  renderEvList("ev-repo-list", ledger.repos || [], "repo");
}

function renderEvList(elId, items, type) {
  const el = document.getElementById(elId);
  if (!items.length) {
    el.innerHTML = '<div class="ev-empty">暂无' +
      (type === "paper" ? "论文" : type === "dataset" ? "数据集" : "工程") +
      '</div>';
    return;
  }
  el.innerHTML = items.map(it => evCardHTML(it, type)).join("");
}

function evCardHTML(it, type) {
  const status = it.review_status || "pending";
  const statusLabel = REVIEW_LABELS[status] || status;
  const sourceMode = it.source_mode || "manual";
  const actions = [
    "pending", "accepted", "core", "background", "rejected", "needs_check",
  ];
  const actionBtns = actions.map(s => {
    const isActive = s === status;
    const isReject = s === "rejected";
    return `<button class="ev-btn ${isActive ? "ev-btn--active" : ""} ${isReject ? "ev-btn--reject" : ""}" data-ev-id="${escapeHtml(it.evidence_id)}" data-action="review" data-status="${s}" type="button">${REVIEW_LABELS[s]}</button>`;
  }).join("");
  const noteHTML = it.user_note
    ? `<div class="ev-card__note">📝 ${escapeHtml(it.user_note)}</div>`
    : "";

  let titleLine = `<div class="ev-card__title">${escapeHtml(it.title || "(无标题)")}</div>`;
  let metaLine = "";

  if (type === "paper") {
    const yr = it.year ? `[${it.year}]` : "";
    const auth = (it.authors || []).slice(0, 2).join(", ") +
      ((it.authors || []).length > 2 ? ` +${it.authors.length - 2}` : "");
    metaLine = `${yr} ${auth ? "· " + escapeHtml(auth) : ""}`.trim();
    if (it.url) metaLine += ` · <a href="${escapeHtml(it.url)}" target="_blank" rel="noopener">arXiv</a>`;
    if (it.doi) metaLine += ` · <a href="https://doi.org/${escapeHtml(it.doi)}" target="_blank" rel="noopener">DOI</a>`;
  } else if (type === "dataset") {
    metaLine = [it.scale, it.license].filter(Boolean).map(escapeHtml).join(" · ");
    if (it.download) metaLine += ` · <a href="${escapeHtml(it.download)}" target="_blank" rel="noopener">下载</a>`;
  } else if (type === "repo") {
    metaLine = [it.license, it.paper_title].filter(Boolean).map(escapeHtml).join(" · ");
    if (it.url) metaLine += ` · <a href="${escapeHtml(it.url)}" target="_blank" rel="noopener">仓库</a>`;
  }

  return `
    <div class="ev-card" data-ev-id="${escapeHtml(it.evidence_id)}">
      <div class="ev-card__head">
        ${titleLine}
        <span class="ev-card__source ev-card__source--${sourceMode}">${sourceMode === "auto_search" ? "自动" : "手动"}</span>
        <span class="ev-card__status ev-card__status--${status}">${statusLabel}</span>
      </div>
      ${metaLine ? `<div class="ev-card__meta">${metaLine}</div>` : ""}
      ${noteHTML}
      <div class="ev-card__actions">
        ${actionBtns}
        <button class="ev-btn ev-btn--danger" data-ev-id="${escapeHtml(it.evidence_id)}" data-action="delete" type="button">🗑️ 删</button>
      </div>
    </div>
  `;
}

async function refreshEvidence() {
  if (!state.projectId) {
    document.getElementById("ev-paper-list").innerHTML =
      '<div class="ev-empty">先到 "一题分析" tab 跑一次分析</div>';
    return;
  }
  document.getElementById("ev-pid").textContent = `project: ${state.projectId}`;
  
  try {
    const r = await fetch(`${API}/api/v1/one-topic/${state.projectId}/evidence`);
    
    if (!r.ok) {
      appendTrace({ type: "warn", name: "evidence fetch", detail: `HTTP ${r.status}` });
      return;
    }
    const ledger = await r.json();
    renderEvidence(ledger);
  } catch (e) {
    appendTrace({ type: "warn", name: "evidence fetch", detail: String(e).slice(0, 200) });
  }
}

async function patchReview(evidenceId, newStatus) {
  if (!state.projectId) return;
  const r = await fetch(`${API}/api/v1/one-topic/evidence/${evidenceId}/review`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ review_status: newStatus }),
  });
  if (!r.ok) {
    const err = await r.text();
    appendTrace({ type: "error", name: "PATCH", detail: err.slice(0, 200) });
    return;
  }
  const data = await r.json();
  if (data.ok) {
    appendTrace({ type: "step", name: "review", detail: `${data.evidence_id} -> ${newStatus}` });
  } else {
    appendTrace({ type: "warn", name: "review", detail: data.message });
  }
  await refreshEvidence();
}

async function deleteEvidence(evidenceId) {
  if (!confirm(`确认删除 ${evidenceId}?`)) return;
  const r = await fetch(`${API}/api/v1/one-topic/evidence/${evidenceId}`, {
    method: "DELETE",
  });
  if (!r.ok) {
    const err = await r.text();
    appendTrace({ type: "error", name: "DELETE", detail: err.slice(0, 200) });
    return;
  }
  const data = await r.json();
  appendTrace({ type: "step", name: "delete", detail: data.message });
  await refreshEvidence();
}

async function addManualPaper(body) {
  const r = await fetch(`${API}/api/v1/one-topic/${state.projectId}/evidence/papers/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return r.json();
}

async function addManualDataset(body) {
  const r = await fetch(`${API}/api/v1/one-topic/${state.projectId}/evidence/datasets/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return r.json();
}

async function addManualRepo(body) {
  const r = await fetch(`${API}/api/v1/one-topic/${state.projectId}/evidence/repos/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return r.json();
}

// ---------- 弹窗 ----------

function showModal(id) { document.getElementById(id).hidden = false; }
function hideModal(id) { document.getElementById(id).hidden = true; }

// ---------- 主入口 ----------

async function onAnalyze() {
  if (state.running) return;
  const topic = document.getElementById("input-topic").value.trim();
  if (!topic) {
    showError("请先输入选题");
    return;
  }
  hideError();
  state.running = true;
  state.result = null;
  state.projectId = "";
  document.getElementById("result-grid").hidden = true;
  const btn = document.getElementById("btn-analyze");
  btn.disabled = true;
  btn.textContent = "⏳ 正在分析...";

  const body = {
    raw_topic: topic,
    major: document.getElementById("input-major").value.trim() || null,
    advisor_direction: document.getElementById("input-advisor").value.trim() || null,
    goal_level: document.getElementById("input-goal").value,
    prefer: document.getElementById("input-prefer").value,
  };

  try {
    const result = await runStream("/api/v1/one-topic/analyze/stream", body);
    if (result) {
      state.result = result;
      state.projectId = result.project_id || "";
      renderResult(result);
      document.getElementById("trace-sub").textContent =
        `完成 · 共 ${state.trace.length} 个 trace 事件 · 耗时 ${result.elapsed_ms || "?"} ms` +
        (state.projectId ? ` · project_id: ${state.projectId}` : "");
      refreshReportSummary();  // Session 8: 自动加载已有 FinalPackage 摘要
    }
  } catch (e) {
    showError(`分析失败: ${String(e).slice(0, 200)}`);
  } finally {
    state.running = false;
    btn.disabled = false;
    btn.textContent = "🚀 开始判断能不能做";
  }
}

function showError(msg) {
  const el = document.getElementById("input-error");
  el.textContent = msg;
  el.hidden = false;
}
function hideError() {
  document.getElementById("input-error").hidden = true;
}

// ---------- 事件绑定 ----------

document.getElementById("btn-analyze").addEventListener("click", onAnalyze);
document.getElementById("input-topic").addEventListener("keydown", (e) => {
  if (e.key === "Enter") onAnalyze();
});
document.getElementById("btn-trace-clear").addEventListener("click", () => {
  state.trace = [];
  renderTraceList();
});
document.getElementById("api-base").textContent = API;

// Tab 切换
document.querySelectorAll(".tab").forEach(t => {
  t.addEventListener("click", () => switchTab(t.dataset.tab));
});

// Evidence page buttons
document.getElementById("tab-evidence").addEventListener("click", () => {
  setTimeout(() => refreshEvidence(), 0);
});
document.getElementById("btn-ev-refresh").addEventListener("click", refreshEvidence);

// 弹窗: 论文
document.getElementById("btn-add-paper").addEventListener("click", () => {
  if (!state.projectId) {
    alert("先到 \"一题分析\" tab 跑一次分析, 再加证据");
    return;
  }
  // 清空
  ["title", "authors", "year", "doi", "arxiv", "url", "abstract", "note"]
    .forEach(k => { document.getElementById("mp-" + k).value = ""; });
  showModal("modal-add-paper");
});
document.getElementById("mp-cancel").addEventListener("click", () => hideModal("modal-add-paper"));
document.getElementById("mp-save").addEventListener("click", async () => {
  const title = document.getElementById("mp-title").value.trim();
  if (!title) { alert("标题必填"); return; }
  const body = {
    title,
    authors: document.getElementById("mp-authors").value.split(",").map(s => s.trim()).filter(Boolean),
    year: parseInt(document.getElementById("mp-year").value) || null,
    doi: document.getElementById("mp-doi").value.trim() || null,
    arxiv_id: document.getElementById("mp-arxiv").value.trim() || null,
    url: document.getElementById("mp-url").value.trim() || null,
    abstract: document.getElementById("mp-abstract").value.trim() || null,
    user_note: document.getElementById("mp-note").value.trim() || null,
  };
  const data = await addManualPaper(body);
  if (data.ok) {
    appendTrace({ type: "step", name: "add-paper", detail: `${data.evidence_id} 入池` });
    hideModal("modal-add-paper");
    refreshEvidence();
  } else {
    alert("入池失败: " + data.message);
  }
});

// 弹窗: 数据集
document.getElementById("btn-add-dataset").addEventListener("click", () => {
  if (!state.projectId) { alert("先跑一次分析"); return; }
  ["name", "scale", "license", "download", "annotation", "note"]
    .forEach(k => { document.getElementById("md-" + k).value = ""; });
  showModal("modal-add-dataset");
});
document.getElementById("md-cancel").addEventListener("click", () => hideModal("modal-add-dataset"));
document.getElementById("md-save").addEventListener("click", async () => {
  const name = document.getElementById("md-name").value.trim();
  if (!name) { alert("名称必填"); return; }
  const body = {
    name,
    scale: document.getElementById("md-scale").value.trim() || null,
    license: document.getElementById("md-license").value.trim() || null,
    download: document.getElementById("md-download").value.trim() || null,
    annotation: document.getElementById("md-annotation").value.trim() || null,
    user_note: document.getElementById("md-note").value.trim() || null,
  };
  const data = await addManualDataset(body);
  if (data.ok) {
    appendTrace({ type: "step", name: "add-dataset", detail: `${data.evidence_id} 入池` });
    hideModal("modal-add-dataset");
    refreshEvidence();
  } else {
    alert("入池失败: " + data.message);
  }
});

// 弹窗: 工程
document.getElementById("btn-add-repo").addEventListener("click", () => {
  if (!state.projectId) { alert("先跑一次分析"); return; }
  ["name", "url", "paper", "license", "note"].forEach(k => { document.getElementById("mr-" + k).value = ""; });
  ["readme", "env", "train", "eval"].forEach(k => { document.getElementById("mr-" + k).checked = false; });
  showModal("modal-add-repo");
});
document.getElementById("mr-cancel").addEventListener("click", () => hideModal("modal-add-repo"));
document.getElementById("mr-save").addEventListener("click", async () => {
  const name = document.getElementById("mr-name").value.trim();
  if (!name) { alert("名称必填"); return; }
  const body = {
    name,
    repository_url: document.getElementById("mr-url").value.trim() || null,
    paper_title: document.getElementById("mr-paper").value.trim() || null,
    license: document.getElementById("mr-license").value.trim() || null,
    user_note: document.getElementById("mr-note").value.trim() || null,
    has_readme: document.getElementById("mr-readme").checked,
    has_env_file: document.getElementById("mr-env").checked,
    has_training_script: document.getElementById("mr-train").checked,
    has_eval_script: document.getElementById("mr-eval").checked,
  };
  const data = await addManualRepo(body);
  if (data.ok) {
    appendTrace({ type: "step", name: "add-repo", detail: `${data.evidence_id} 入池` });
    hideModal("modal-add-repo");
    refreshEvidence();
  } else {
    alert("入池失败: " + data.message);
  }
});

// ---------- Session 3: Human Gate 1-2 (regenerate) ----------

function _parseList(s) {
  return (s || "").split(/[,\n]/).map(x => x.trim()).filter(Boolean);
}

async function regenerate(useConfirmedKw, useConfirmedPlan) {
  if (!state.projectId) {
    alert("先跑一次分析");
    return;
  }
  const body = {
    raw_topic: document.getElementById("input-topic").value.trim(),
    major: document.getElementById("input-major").value.trim() || null,
    advisor_direction: document.getElementById("input-advisor").value.trim() || null,
    goal_level: document.getElementById("input-goal").value,
    prefer: document.getElementById("input-prefer").value,
  };
  if (useConfirmedKw) body.confirmed_keywords = useConfirmedKw;
  if (useConfirmedPlan) body.confirmed_search_plan = useConfirmedPlan;

  appendTrace({ type: "step", name: "regenerate", detail: "用确认版关键词/检索词重跑" });
  try {
    const r = await fetch(`${API}/api/v1/one-topic/${state.projectId}/regenerate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.text();
      appendTrace({ type: "error", name: "regenerate", detail: err.slice(0, 300) });
      showError("regenerate 失败: " + err.slice(0, 200));
      return;
    }
    const data = await r.json();
    state.result = data;
    state.projectId = data.project_id || state.projectId;
    renderResult(data);
    document.getElementById("trace-sub").textContent =
      `regenerate 完成 · ${data.elapsed_ms || "?"} ms`;
  } catch (e) {
    showError("regenerate 异常: " + String(e).slice(0, 200));
  }
}

// Session 3 关键词/检索词编辑: 用事件代理绑在 document 上
document.addEventListener("click", async (e) => {
  // Session 7: ref-action 按钮优先匹配 (ref cards 在 data-action 区域外)
  const refBtn = e.target.closest("[data-ref-action]");
  if (refBtn) {
    if (!state.projectId) {
      alert("请先跑一次分析");
      return;
    }
    const action = refBtn.dataset.refAction;
    const evidenceId = refBtn.dataset.evidenceId;

    const card = refBtn.closest(".ref-card");
    const wpCard = refBtn.closest(".wp-card");
    const pivotCard = refBtn.closest(".pivot-card");
    const checkDiv = refBtn.closest(".review__check");
    let target_type = "feasibility", target_id = "main";
    if (wpCard) {
      target_type = "work_package";
      target_id = wpCard.dataset.wpId;
    } else if (pivotCard) {
      target_type = "pivot_route";
      target_id = pivotCard.dataset.pivotLevel;
    } else if (checkDiv) {
      target_type = "review_check";
      target_id = checkDiv.dataset.checkDim;
    }

    const reason = prompt(`复核理由 (${action} ${evidenceId}):`, "");
    if (reason === null) return;

    refBtn.disabled = true;
    const _orig = refBtn.textContent;
    refBtn.textContent = "⏳ ...";
    try {
      const resp = await reviewRef(state.projectId, target_type, target_id, evidenceId, action, reason);
      if (resp && resp.ok) {
        refBtn.textContent = "✓";
        if (card && card.parentNode) {
          card.style.opacity = "0.3";
        }
        const cov = await refreshRefs(state.projectId);
        if (cov) {
          appendTrace({
            type: "step", name: "coverage-update",
            detail: `coverage=${cov.coverage_score.toFixed(2)}`,
          });
        }
      } else {
        refBtn.textContent = "✗ " + (resp ? resp.message : "fail");
        setTimeout(() => { refBtn.textContent = _orig; refBtn.disabled = false; }, 3000);
      }
    } catch (err) {
      refBtn.textContent = "✗ " + err.message;
      refBtn.disabled = false;
    }
    return;
  }

  const t = e.target.closest("[data-action], #btn-edit-keywords, #btn-edit-search-plan, #kw-cancel, #kw-regen, #sp-cancel, #sp-regen, #btn-show-pivots, #pivot-cancel, #btn-rescore, [data-pivot-level]");
  if (!t) return;
  const id = t.id;

  if (id === "btn-edit-keywords") {
    if (!state.result) return;
    const kb = state.result.keyword_breakdown || {};
    document.getElementById("kw-method").value = (kb.method_keywords || []).join(", ");
    document.getElementById("kw-task").value = (kb.task_keywords || []).join(", ");
    document.getElementById("kw-object").value = (kb.object_keywords || []).join(", ");
    document.getElementById("kw-scenario").value = (kb.scenario_keywords || []).join(", ");
    document.getElementById("kw-metric").value = (kb.metric_keywords || []).join(", ");
    document.getElementById("kw-risk").value = (kb.risk_terms || []).join(", ");
    showModal("modal-edit-keywords");
  } else if (id === "kw-cancel") {
    hideModal("modal-edit-keywords");
  } else if (id === "kw-regen") {
    const kw = {
      method_keywords: _parseList(document.getElementById("kw-method").value),
      task_keywords: _parseList(document.getElementById("kw-task").value),
      object_keywords: _parseList(document.getElementById("kw-object").value),
      scenario_keywords: _parseList(document.getElementById("kw-scenario").value),
      metric_keywords: _parseList(document.getElementById("kw-metric").value),
      risk_terms: _parseList(document.getElementById("kw-risk").value),
      query_keywords_zh: [], query_keywords_en: [],
    };
    hideModal("modal-edit-keywords");
    await regenerate(kw, null);
  } else if (id === "btn-edit-search-plan") {
    if (!state.result) return;
    const sp = state.result.search_plan || {};
    document.getElementById("sp-papers").value = (sp.paper_queries || []).join("\n");
    document.getElementById("sp-datasets").value = (sp.dataset_queries || []).join("\n");
    document.getElementById("sp-eng").value = (sp.engineering_queries || []).join("\n");
    showModal("modal-edit-search-plan");
  } else if (id === "sp-cancel") {
    hideModal("modal-edit-search-plan");
  } else if (id === "btn-show-pivots") {
    showPivotModal();
  } else if (id === "pivot-cancel") {
    hideModal("modal-pivot");
  } else if (id === "sp-regen") {
    const plan = {
      paper_queries: _parseList(document.getElementById("sp-papers").value),
      dataset_queries: _parseList(document.getElementById("sp-datasets").value),
      engineering_queries: _parseList(document.getElementById("sp-eng").value),
    };
    plan.query_total = plan.paper_queries.length + plan.dataset_queries.length + plan.engineering_queries.length;
    hideModal("modal-edit-search-plan");
    await regenerate(null, plan);
  } else if (id === "btn-rescore") {
    // Session 5 §7.3: 重新评分证据 (不改变 review_status)
    if (!state.projectId) {
      alert("请先跑一次分析");
      return;
    }
    t.disabled = true;
    const _orig = t.textContent;
    t.textContent = "⏳ 评分中...";
    try {
      const r1 = await fetch(`${API}/api/v1/one-topic/${state.projectId}/evidence/rescore`, {method: "POST"});
      if (!r1.ok) throw new Error(`HTTP ${r1.status}`);
      const rr = await r1.json();
      const r2 = await fetch(`${API}/api/v1/one-topic/${state.projectId}/evidence/score-summary`);
      if (!r2.ok) throw new Error(`HTTP ${r2.status}`);
      const sm = await r2.json();
      t.textContent = `✓ 已更新 (paper ${rr.summary.avg_paper_score}, dataset ${rr.summary.avg_dataset_score}, repo ${rr.summary.avg_repo_score}; usable: ${sm.usable_papers}P ${sm.usable_datasets}D ${sm.usable_repos}R)`;
      setTimeout(() => { t.textContent = _orig; t.disabled = false; }, 5000);
    } catch (err) {
      t.textContent = "✗ 失败: " + err.message;
      t.disabled = false;
    }
  } else if (t.dataset.refAction) {
    // Session 7 §7.3: 用户复核 EvidenceRef (duplicate guard, handled above)
    return;
  }
});

document.addEventListener("change", (e) => {
  // Session 5 §7.2: 证据按评分/年份排序
  if (e.target && e.target.id === "sort-papers") {
    const mode = e.target.value;
    const list = document.querySelector('[data-evidence-list="papers"]');
    if (!list) return;
    const cards = Array.from(list.querySelectorAll(".evidence-card"));
    const getScore = (c) => {
      const m = (c.querySelector(".evidence-card__score") || {}).textContent || "";
      const mm = m.match(/[\d.]+/);
      return mm ? parseFloat(mm[0]) : 0;
    };
    const getYear = (c) => {
      const m = (c.querySelector(".evidence-card__meta") || {}).textContent || "";
      const mm = m.match(/\[(\d{4})\]/);
      return mm ? parseInt(mm[1]) : 0;
    };
    cards.sort((a, b) => {
      if (mode === "score-desc") return getScore(b) - getScore(a);
      if (mode === "score-asc") return getScore(a) - getScore(b);
      if (mode === "year-desc") return getYear(b) - getYear(a);
      if (mode === "year-asc") return getYear(a) - getYear(b);
      return 0;
    });
    cards.forEach(c => list.appendChild(c));
  }
});

function showPivotModal() {
  if (!state.result || !state.projectId) {
    alert("先跑一次分析");
    return;
  }
  const routes = (state.result.proposal_recommendation || {}).pivot_routes || [];
  if (routes.length === 0) {
    alert("当前 verdict 无需退化路线 (已是 可做)");
    return;
  }
  const html = routes.map(r => {
    const refsHtml = renderEvidenceRefs(r.evidence_refs || [], { target_type: "pivot_route", target_id: r.level });
    const riskHtml = (r.risk_reduction_refs && r.risk_reduction_refs.length)
      ? `<details class="pivot-card__risk-refs"><summary>📉 风险降低 (${r.risk_reduction_refs.length})</summary>${renderEvidenceRefs(r.risk_reduction_refs, {})}</details>` : "";
    const missingHtml = (r.missing_evidence && r.missing_evidence.length)
      ? `<div class="pivot-card__missing"><div class="pivot-card__missing-title">⚠ 缺口</div><ul>${r.missing_evidence.map(x => `<li>${escapeHtml(x)}</li>`).join("")}</ul></div>` : "";
    return `
    <div class="pivot-card" data-pivot-level="${r.level}">
      <div class="pivot-card__head">
        <span class="pivot-card__level pivot-card__level--${r.level}">${r.level}</span>
        <div class="pivot-card__title">${escapeHtml(r.new_topic)}</div>
        <span class="pivot-card__conf">conf=${(r.confidence || 0).toFixed(2)}</span>
      </div>
      <div class="pivot-card__tradeoff">${escapeHtml(r.tradeoff)}</div>
      <div class="pivot-card__keywords">
        ${(r.preserved_keywords || []).map(k => `<span class="pivot-card__kw">✓ ${escapeHtml(k)}</span>`).join("")}
        ${(r.removed_keywords || []).map(k => `<span class="pivot-card__kw pivot-card__kw--removed">✗ ${escapeHtml(k)}</span>`).join("")}
      </div>
      <details class="pivot-card__refs" open>
        <summary>🔗 路线引用 (${(r.evidence_refs || []).length})</summary>
        ${refsHtml}
      </details>
      ${riskHtml}
      ${missingHtml}
      <div class="pivot-card__select">
        <button id="btn-select-pivot-${r.level}" data-pivot-level="${r.level}" type="button">✓ 选这条路</button>
      </div>
    </div>
  `;
  }).join("");
  document.getElementById("pivot-list").innerHTML = html;
  showModal("modal-pivot");
}

async function selectPivotRoute(level) {
  if (!state.projectId) return;
  const routes = (state.result.proposal_recommendation || {}).pivot_routes || [];
  const route = routes.find(r => r.level === level);
  if (!route) {
    alert("未找到路线 " + level);
    return;
  }
  hideModal("modal-pivot");
  appendTrace({ type: "step", name: "select-pivot", detail: "选 " + level });
  try {
    const r = await fetch(`${API}/api/v1/one-topic/${state.projectId}/pivot/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(route),
    });
    if (!r.ok) {
      const err = await r.text();
      showError("选路线失败: " + err.slice(0, 200));
      return;
    }
    const rec = await r.json();
    // 替换 state.result 的 recommendation, 重渲
    state.result = { ...state.result, proposal_recommendation: rec };
    renderResult(state.result);
    appendTrace({ type: "step", name: "pivot-applied", detail: "已用 " + level + " 路线生成新工作包" });
  } catch (e) {
    showError("选路线异常: " + String(e).slice(0, 200));
  }
}

// 事件代理: ev-card 内的按钮
document.body.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-action], [data-pivot-level]");
  if (btn) {
    const action = btn.dataset.action;
    const eid = btn.dataset.evId;
    if (action === "review") {
      await patchReview(eid, btn.dataset.status);
    } else if (action === "delete") {
      await deleteEvidence(eid);
    } else if (action === "select-pivot") {
      await selectPivotRoute(btn.dataset.level);
    } else if (btn.dataset.pivotLevel) {
      await selectPivotRoute(btn.dataset.pivotLevel);
    }
    return;
  }
  // Session 8: 报告区按钮
  const id = e.target.id;
  if (id === "btn-build-report" || id === "btn-rebuild-report") {
    await buildReport();
  } else if (id === "btn-download-report") {
    downloadReport();
  } else if (id === "btn-preview-report") {
    toggleReportPreview();
  }
});
