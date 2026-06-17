// TopicPilot-CN OneTopic MVP — 极简前端
// 流程: 输入题目 → 调 POST /analyze/stream → 边推 trace 边渲 5 区结果

const API = "http://127.0.0.1:18181";

const state = {
  result: null,
  trace: [],
  streamAbort: null,
  running: false,
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

// ---------- SSE 流 ----------

async function runStream(endpoint, body) {
  if (state.streamAbort) state.streamAbort.abort();
  state.streamAbort = new AbortController();
  state.trace = [];
  renderTraceList();
  document.getElementById("trace-sub").textContent = `正在调 ${endpoint} ...`;

  const r = await fetch(API + endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
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

// ---------- 结果渲染 ----------

function renderResult(r) {
  document.getElementById("result-grid").hidden = false;

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

  // Block 3: 证据
  const ev = r.evidence_summary || {};
  const paperCards = (ev.papers || []).map(p => `
    <div class="evidence-card">
      <div class="evidence-card__title">${escapeHtml((p.title || "").slice(0, 100))}
        <span class="evidence-card__source evidence-card__source--${p.source}">${p.source}</span>
      </div>
      <div class="evidence-card__meta">${p.year ? `[${p.year}]` : ""}${(p.authors && p.authors.length) ? " · " + escapeHtml(p.authors.slice(0, 3).join(", ")) : ""}</div>
      ${p.url ? `<a href="${escapeHtml(p.url)}" target="_blank" rel="noopener">📄 arXiv</a>` : ""}
    </div>
  `).join("") || '<div class="evidence-empty">暂无论文</div>';
  const datasetCards = (ev.datasets || []).map(d => `
    <div class="evidence-card">
      <div class="evidence-card__title">${escapeHtml(d.name || d.dataset_id)}
        <span class="evidence-card__source evidence-card__source--${d.source}">${d.source}</span>
      </div>
      <div class="evidence-card__meta">规模: ${escapeHtml(d.scale || "未知")} · 契合度: ${escapeHtml(d.fit || "中")}</div>
      ${d.download ? `<a href="${escapeHtml(d.download)}" target="_blank" rel="noopener">⬇️ 下载</a>` : ""}
    </div>
  `).join("") || '<div class="evidence-empty">暂无数据集</div>';
  const baselineCards = (ev.baselines || []).map(b => `
    <div class="evidence-card">
      <div class="evidence-card__title">${escapeHtml(b.name || b.baseline_id)}
        <span class="evidence-card__source evidence-card__source--${b.source}">${b.source}</span>
      </div>
      <div class="evidence-card__meta">复现难度: ${escapeHtml(b.reproduce_difficulty || "中")}</div>
      ${b.repository_url ? `<a href="${escapeHtml(b.repository_url)}" target="_blank" rel="noopener">🔗 仓库</a>` : ""}
    </div>
  `).join("") || '<div class="evidence-empty">暂无 baseline</div>';

  document.getElementById("block-evidence").innerHTML = `
    <div class="evidence-section">
      <div class="evidence-section__title">📚 论文 <span class="evidence-section__count">${ev.paper_count || 0}</span> (arXiv 真实 ${ev.arxiv_paper_count || 0})</div>
      <div class="evidence-list">${paperCards}</div>
    </div>
    <div class="evidence-section">
      <div class="evidence-section__title">💾 数据集 <span class="evidence-section__count">${ev.dataset_count || 0}</span></div>
      <div class="evidence-list">${datasetCards}</div>
    </div>
    <div class="evidence-section">
      <div class="evidence-section__title">⚙️ Baseline <span class="evidence-section__count">${ev.baseline_count || 0}</span></div>
      <div class="evidence-list">${baselineCards}</div>
    </div>
    <div class="evidence-section">
      <div class="evidence-section__title">📏 评价指标: ${(ev.metrics || []).map(escapeHtml).join("、") || "无"}</div>
    </div>
  `;

  // Block 4: 可行性
  const feas = r.feasibility || {};
  document.getElementById("block-feasibility").innerHTML = `
    <div class="feasibility__verdict feasibility__verdict--${escapeHtml(feas.verdict || "暂缓")}">${escapeHtml(feas.verdict || "暂缓")}</div>
    <div class="feasibility__reason">${escapeHtml(feas.reason || "")}</div>
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
    <div class="feasibility__next">${escapeHtml(feas.recommended_next_action || "")}</div>
  `;

  // Block 5: 开题建议 + 审核
  const rec = r.proposal_recommendation || {};
  const rev = r.light_review || {};
  const wpHtml = (rec.work_packages || []).map(wp => `
    <div class="wp-card">
      <div class="wp-card__id">${escapeHtml(wp.wp_id)} · ${escapeHtml(wp.chapter || "")}</div>
      <div class="wp-card__title">${escapeHtml(wp.title || "")}</div>
      <div class="wp-card__detail"><strong>问题:</strong> ${escapeHtml(wp.research_question || "")}</div>
      <div class="wp-card__detail"><strong>方法:</strong> ${escapeHtml(wp.method_approach || "")}</div>
      <div class="wp-card__detail"><strong>数据:</strong> ${escapeHtml(wp.data_source || "")}</div>
      <div class="wp-card__detail"><strong>实验:</strong> ${escapeHtml(wp.experiment_plan || "")}</div>
    </div>
  `).join("");
  const checksHtml = (rev.checks || []).map(c => `
    <div class="review__check">
      <div class="review__check-dim">${escapeHtml(c.dimension)}</div>
      <div class="review__check-result review__check-result--${escapeHtml(c.result)}">${escapeHtml(c.result)}</div>
      <div class="review__check-comment">${escapeHtml(c.comment || "")}</div>
    </div>
  `).join("");
  const checklistHtml = (rev.revision_checklist || []).map(x => `<li>${escapeHtml(x)}</li>`).join("");
  document.getElementById("block-recommendation").innerHTML = `
    <div class="proposal__topic">📌 ${escapeHtml(rec.recommended_topic || "")}</div>
    <div class="proposal__reason">
      推荐理由:
      <ul>${(rec.recommendation_reason || []).map(x => `<li>${escapeHtml(x)}</li>`).join("")}</ul>
    </div>
    <div class="wp-list">${wpHtml}</div>
    <details class="outline-list">
      <summary>📋 开题结构 (8 节)</summary>
      <ol>${(rec.proposal_outline || []).map(x => `<li>${escapeHtml(x)}</li>`).join("")}</ol>
    </details>
    <div class="review__verdict review__verdict--${escapeHtml(rev.verdict || "需修改")}">🛡️ ${escapeHtml(rev.verdict || "需修改")}</div>
    <div class="review__summary">${escapeHtml(rev.summary || "")}</div>
    <div class="review__checks">${checksHtml}</div>
    <div class="review__checklist-title">📝 修改清单</div>
    <ol class="review__checklist">${checklistHtml}</ol>
  `;
}

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
      renderResult(result);
      document.getElementById("trace-sub").textContent =
        `完成 · 共 ${state.trace.length} 个 trace 事件 · 耗时 ${result.elapsed_ms || "?"} ms`;
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

document.getElementById("btn-analyze").addEventListener("click", onAnalyze);
document.getElementById("input-topic").addEventListener("keydown", (e) => {
  if (e.key === "Enter") onAnalyze();
});
document.getElementById("btn-trace-clear").addEventListener("click", () => {
  state.trace = [];
  renderTraceList();
});
document.getElementById("api-base").textContent = API;
