// TopicPilot-CN MVP 静态前端逻辑
// 不使用任何前端框架, 直接 fetch + DOM 操作
// 状态机: project_id + 每 Phase 状态 + 每 Phase payload 缓存 (供右侧栏读)

const API = "http://127.0.0.1:18181";
const state = {
  project_id: null,
  phase_status: {
    "01": false, "02": false, "03": false, "04": false,
    "05": false, "06": false, "07-proposal": false, "07-committee": false, "08": false,
  },
  blocked: false,
  // 每 Phase 缓存最后一次成功响应 payload (后端原始格式)
  intake: null,         // Phase 01: create project 响应 (含 .payload)
  topicSpec: null,      // Phase 02: decompose / get-spec
  searchPlan: null,     // Phase 03: search-plan / get-plan
  evidenceLedger: null, // Phase 04: evidence-build / get-ledger
  riskEvaluation: null, // Phase 05
  workPackage: null,    // Phase 06
  proposalDraft: null,  // Phase 07 proposal
  committeeReview: null,// Phase 07 committee
  finalPackage: null,   // Phase 08
  currentSidebarPhase: 0, // 0 = 未启动, 1-8 = 当前 phase
};

// ------- 工具函数 -------

function setOutput(phaseId, text, level = "ok") {
  const el = document.getElementById(`out-${phaseId}`);
  el.className = `phase-output ${level}`;
  el.textContent = text;
}

function enablePhase(phaseNum) {
  const card = document.getElementById(`phase-0${phaseNum}`);
  card.classList.remove("disabled");
  card.querySelectorAll("button[data-action]").forEach(b => b.disabled = false);
}

function showBlockBanner(detail) {
  const banner = document.getElementById("block-banner");
  document.getElementById("block-banner-detail").textContent = detail;
  banner.classList.remove("hidden");
  state.blocked = true;
  for (let i = 2; i <= 8; i++) {
    const card = document.getElementById(`phase-0${i}`);
    if (card) card.classList.add("disabled");
  }
}

async function postJSON(path, body = {}) {
  const r = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return { status: r.status, data: r.status < 400 ? await r.json() : await r.text() };
}

async function getJSON(path) {
  const r = await fetch(API + path);
  return { status: r.status, data: r.status < 400 ? await r.json() : await r.text() };
}

function summarize(obj, keys) {
  const lines = [];
  for (const k of keys) {
    if (obj[k] !== undefined) {
      const v = obj[k];
      lines.push(`${k}: ${typeof v === "object" ? JSON.stringify(v).slice(0, 80) : v}`);
    }
  }
  return lines.join(" | ");
}

// ------- 右侧栏渲染 -------

function setSidebar(phaseNum, title, rows, extras) {
  state.currentSidebarPhase = phaseNum;
  document.getElementById("sidebar-title").textContent = title;
  const sub = {
    0: "完成 Phase 01 后这里实时显示每步关键字段",
    1: "项目建档 + 毕业目标 + 评级",
    2: "题目结构化 + 风险词 + 工作包草稿",
    3: "7 层检索词 + 方向成熟度",
    4: "论文 / 数据 / Baseline / 评价 (含 arXiv 真实论文)",
    5: "6 维风险 + Pivot 候选 + 决策",
    6: "最终题目 + 工作包 + 实验矩阵",
    7: "开题报告 + 委员会 7 维度 + 3 角色对话",
    8: "MVP 验收 + Markdown 导出",
  }[phaseNum] || "";
  document.getElementById("sidebar-sub").textContent = sub;

  const fields = document.getElementById("sidebar-fields");
  if (!rows || rows.length === 0) {
    fields.innerHTML = '<div class="sidebar-empty">尚无数据</div>';
  } else {
    fields.innerHTML = rows.map(([k, v]) =>
      `<div class="sidebar-row"><span class="k">${k}</span><span class="v">${v}</span></div>`
    ).join("");
  }
  document.getElementById("sidebar-extras").innerHTML = extras || "";
}

function renderSidebar(phaseNum) {
  switch (phaseNum) {
    case 1: return _renderSidebar01();
    case 2: return _renderSidebar02();
    case 3: return _renderSidebar03();
    case 4: return _renderSidebar04();
    case 5: return _renderSidebar05();
    case 6: return _renderSidebar06();
    case 7: return _renderSidebar07();
    case 8: return _renderSidebar08();
    default: return setSidebar(0, "当前阶段：未启动", [], "");
  }
}

function _renderSidebar01() {
  const p = state.intake;
  if (!p) return setSidebar(1, "Phase 01 · 待创建", [], "");
  const payload = p.payload || {};
  setSidebar(1, "Phase 01 · 建档完成", [
    ["项目 ID", p.id],
    ["case_id", payload.case_id || "-"],
    ["intake_rating", payload.intake_rating || "-"],
    ["目标档位", payload.goal_level || "-"],
    ["学位", payload.degree_type || "-"],
    ["导师方向", payload.advisor_direction || "-"],
    ["开题时间", payload.proposal_deadline || "-"],
    ["毕业时间", payload.thesis_deadline || "-"],
    ["原始题目", (payload.raw_topic || "").slice(0, 30) + "..."],
  ]);
}

function _renderSidebar02() {
  const p = state.topicSpec;
  if (!p) return setSidebar(2, "Phase 02 · 待拆解", [], "");
  setSidebar(2, "Phase 02 · 题目拆解", [
    ["normalized_topic", (p.normalized_topic || "").slice(0, 28) + "..."],
    ["task_count", (p.task_type || []).length],
    ["method_count", (p.method_family || []).length],
    ["data_count", (p.data_requirement || []).length],
    ["metric_count", (p.evaluation_metrics || []).length],
    ["decomposition_rating", p.decomposition_rating || "-"],
    ["allow_proceed", String(p.allow_proceed_to_phase03)],
  ]);
}

function _renderSidebar03() {
  const p = state.searchPlan;
  if (!p) return setSidebar(3, "Phase 03 · 待生成", [], "");
  const layers = p.query_layers || [];
  const total = layers.reduce((s, l) => s + (l.queries || []).length, 0);
  setSidebar(3, "Phase 03 · 检索计划", [
    ["maturity_rating", p.maturity_rating || "-"],
    ["layer_count", layers.length],
    ["query_total", total],
    ["top_layer", layers[0]?.layer + ": " + (layers[0]?.title || "").slice(0, 12)],
    ["sample_query", (layers[0]?.queries?.[0] || "").slice(0, 30)],
    ["allow_proceed", String(p.allow_proceed_to_phase04)],
  ]);
}

function _renderSidebar04() {
  const p = state.evidenceLedger;
  if (!p) return setSidebar(4, "Phase 04 · 待构建", [], "");
  const papers = p.papers || [];
  const arxiv = papers.filter(x => x.source === "arXiv");
  const years = papers.map(x => x.year).filter(y => typeof y === "number");
  const datasets = p.datasets || [];
  const baselines = p.baselines || [];
  const extras = arxiv.length ? arxiv.slice(0, 3).map(a =>
    `<div class="arxiv-mini">` +
    `<a href="${a.url || '#'}" target="_blank" rel="noopener">[${a.year || '?'}] ${(a.title || '').slice(0, 40)}</a>` +
    `</div>`
  ).join("") : "";
  setSidebar(4, "Phase 04 · 证据账本", [
    ["evidence_rating", p.evidence_rating || "-"],
    ["paper_count", papers.length],
    ["arxiv_papers", arxiv.length],
    ["latest_year", years.length ? Math.max(...years) : "-"],
    ["dataset_count", datasets.length],
    ["baseline_count", baselines.length],
    ["metric_count", (p.metrics || []).length],
  ], arxiv.length ? "<h3 style='margin-top:10px;font-size:12px;color:#6b7280;'>arXiv 真实论文 (top 3)</h3>" + extras : "");
}

function _renderSidebar05() {
  const p = state.riskEvaluation;
  if (!p) return setSidebar(5, "Phase 05 · 待评估", [], "");
  const rs = p.risk_score || {};
  setSidebar(5, "Phase 05 · 风险评分", [
    ["overall_rating", p.overall_rating || "-"],
    ["overall_score", typeof rs.overall_score === "number" ? rs.overall_score.toFixed(1) : "-"],
    ["decision", p.decision || "-"],
    ["max_risk_dim", p.max_risk_dimension || "-"],
    ["pivot_count", (p.pivot_candidates || []).length],
    ["top_pivot", (p.pivot_candidates?.[0]?.to_topic || "-").slice(0, 30)],
  ]);
}

function _renderSidebar06() {
  const p = state.workPackage;
  if (!p) return setSidebar(6, "Phase 06 · 待定稿", [], "");
  setSidebar(6, "Phase 06 · 工作包", [
    ["final_topic", (p.final_topic || "").slice(0, 30) + "..."],
    ["from_pivot", String(p.from_pivot)],
    ["WP_count", p.work_package_count || (p.work_packages || []).length],
    ["experiment_count", p.experiment_count || (p.experiment_matrices || []).length],
    ["chapter_count", (p.thesis_outline || []).length],
    ["max_writing_risk", p.max_writing_risk || "-"],
  ]);
}

function _renderSidebar07() {
  const p = state.proposalDraft || state.committeeReview;
  if (!p && !state.committeeReview) return setSidebar(7, "Phase 07 · 待生成", [], "");
  const proposal = state.proposalDraft;
  const comm = state.committeeReview;
  const disc = comm?.discussion || [];
  const extras = disc.length ? disc.map(d =>
    `<div class="discussion-bubble ${d.role}">` +
    `<div class="role ${d.role}"></div>` +
    `<div class="body">${(d.comment || "").slice(0, 220)}${(d.comment || "").length > 220 ? "..." : ""}</div>` +
    `</div>`
  ).join("") : "";
  setSidebar(7, "Phase 07 · 开题报告 + 委员会", [
    ["proposal_sections", proposal?.section_count || (proposal?.proposal_sections || []).length],
    ["innovation_count", proposal?.innovation_count || (proposal?.innovation_points || []).length],
    ["committee_verdict", comm?.overall_verdict || "-"],
    ["proposal_maturity", comm?.proposal_maturity || "-"],
    ["review_count", comm?.review_count || (comm?.reviews || []).length],
    ["question_count", comm?.question_count || (comm?.questions || []).length],
    ["discussion_count", disc.length],
  ], extras ? "<h3 style='margin-top:10px;font-size:12px;color:#6b7280;'>委员会 3 角色对话</h3>" + extras : "");
}

function _renderSidebar08() {
  const p = state.finalPackage;
  if (!p) return setSidebar(8, "Phase 08 · 待组装", [], "");
  setSidebar(8, "Phase 08 · 最终材料", [
    ["ready_for_thesis", String(p.ready_for_thesis)],
    ["backend", p.backend_verification || "-"],
    ["ui", p.ui_verification || "-"],
    ["playwright", p.playwright_verification || "-"],
    ["markdown_chars", p.proposal_markdown_chars + " chars"],
    ["allow_proceed", String(p.allow_proceed_to_phase09 ?? "-")],
  ]);
}

// ------- Phase 01: 建档 -------

document.getElementById("intake-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const intake = {
    case_id: fd.get("case_id") + "_" + Date.now().toString().slice(-6),
    major: fd.get("major"),
    degree_type: fd.get("degree_type"),
    goal_level: fd.get("goal_level"),
    thesis_deadline: fd.get("thesis_deadline"),
    proposal_deadline: fd.get("proposal_deadline"),
    first_result_deadline: fd.get("first_result_deadline"),
    advisor_direction: fd.get("advisor_direction"),
    school_requirements: ["必须中文文献"],
    inherited_resources: [],
    student_resources: {
      programming_level: "熟练",
      dl_or_algorithm_foundation: "中",
      paper_reading_ability: "中",
      english_reading_ability: "中",
      compute_resource: "笔记本 3060",
      weekly_hours: parseInt(fd.get("weekly_hours")) || 25,
      data_collection_ability: "中",
      data_annotation_ability: "中",
      code_reproduction_ability: "中",
      system_dev_ability: "中",
    },
    raw_topic: fd.get("raw_topic"),
    must_keep: (fd.get("must_keep") || "").split(",").map(s => s.trim()).filter(Boolean),
    can_drop: [],
    missing_fields: [],
    intake_rating: "A",
  };
  const { status, data } = await postJSON("/api/v1/projects", { intake });
  if (status === 201) {
    state.project_id = data.id;
    state.intake = data;
    setOutput("01", "✓ Phase 01 建档成功\n" + summarize(data, ["id", "case_id"]) +
      "\nrating=" + data.payload.intake_rating);
    renderSidebar(1);
    const v = await postJSON(`/api/v1/projects/${state.project_id}/intake/validate`);
    if (v.status === 200 && v.data.outcome === "OK") {
      state.phase_status["01"] = true;
      enablePhase(2);
    } else {
      showBlockBanner(`outcome=${v.data.outcome} rating=${v.data.intake_rating}`);
    }
  } else {
    setOutput("01", "✗ 建档失败: HTTP " + status + "\n" + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});

// ------- 通用按钮绑定 -------

function bindPhaseAction(phaseNum, action, handler) {
  const card = document.getElementById(`phase-0${phaseNum}`);
  if (!card) return;
  card.querySelectorAll(`button[data-action="${action}"]`).forEach(btn => {
    btn.addEventListener("click", () => {
      if (!state.project_id) {
        setOutput(`0${phaseNum}`, "✗ 请先创建项目 (Phase 01)", "error");
        return;
      }
      if (state.blocked) {
        setOutput(`0${phaseNum}`, "✗ Phase 01 已阻断, 无法继续", "error");
        return;
      }
      handler();
    });
  });
}

// Phase 02
bindPhaseAction(2, "decompose", async () => {
  const { status, data } = await postJSON(
    `/api/v1/projects/${state.project_id}/topic/decompose`,
    { prefer: "heuristic" }
  );
  if (status === 200) {
    state.phase_status["02"] = true;
    state.topicSpec = data.payload || data;
    enablePhase(3);
    setOutput("02", "✓ 题目拆解完成\n" + summarize(data, ["decomposition_rating", "allow_proceed_to_phase03"]));
    renderSidebar(2);
  } else {
    setOutput("02", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});
bindPhaseAction(2, "get-spec", async () => {
  const { status, data } = await getJSON(`/api/v1/projects/${state.project_id}/topic/spec`);
  if (status === 200) {
    state.topicSpec = data.payload || data;
    setOutput("02", "TopicSpec:\n" + JSON.stringify(data.payload, null, 2).slice(0, 800));
    renderSidebar(2);
  } else {
    setOutput("02", "✗ HTTP " + status, "error");
  }
});

// Phase 03
bindPhaseAction(3, "search-plan", async () => {
  const { status, data } = await postJSON(`/api/v1/projects/${state.project_id}/search/plan`);
  if (status === 200) {
    state.phase_status["03"] = true;
    state.searchPlan = data.payload || data;
    enablePhase(4);
    setOutput("03", "✓ 检索计划生成\n" + summarize(data, ["maturity_rating", "allow_proceed_to_phase04"]));
    renderSidebar(3);
  } else {
    setOutput("03", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});
bindPhaseAction(3, "get-plan", async () => {
  const { status, data } = await getJSON(`/api/v1/projects/${state.project_id}/search/plan`);
  if (status === 200) {
    state.searchPlan = data.payload || data;
    const layers = data.payload.query_layers.length;
    const total = data.payload.query_layers.reduce((s, l) => s + l.queries.length, 0);
    setOutput("03", `检索计划: ${layers} 层, ${total} 个总检索词\n` +
      JSON.stringify(data.payload.query_layers.map(l => `${l.layer}: ${l.title}`), null, 2));
    renderSidebar(3);
  } else {
    setOutput("03", "✗ HTTP " + status, "error");
  }
});

// Phase 04
bindPhaseAction(4, "evidence-build", async () => {
  const { status, data } = await postJSON(
    `/api/v1/projects/${state.project_id}/evidence/build`,
    { prefer: "heuristic" }
  );
  if (status === 200) {
    state.phase_status["04"] = true;
    state.evidenceLedger = data.payload || data;
    enablePhase(5);
    setOutput("04",
      "✓ 证据账本生成\n" +
      `rating: ${data.evidence_rating}\n` +
      `papers: ${data.paper_count} (含 arXiv ${(data.payload?.papers || []).filter(p => p.source === 'arXiv').length} 篇) | ` +
      `datasets: ${data.dataset_count} | baselines: ${data.baseline_count} | metrics: ${data.metric_count}`
    );
    renderSidebar(4);
  } else {
    setOutput("04", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});
bindPhaseAction(4, "get-ledger", async () => {
  const { status, data } = await getJSON(`/api/v1/projects/${state.project_id}/evidence/ledger`);
  if (status === 200) {
    state.evidenceLedger = data.payload || data;
    setOutput("04", "EvidenceLedger:\n" + JSON.stringify(data.payload, null, 2).slice(0, 800));
    renderSidebar(4);
  } else {
    setOutput("04", "✗ HTTP " + status, "error");
  }
});

// Phase 05
bindPhaseAction(5, "risk-evaluate", async () => {
  const { status, data } = await postJSON(
    `/api/v1/projects/${state.project_id}/risk/evaluate`,
    { prefer: "heuristic" }
  );
  if (status === 200) {
    state.phase_status["05"] = true;
    state.riskEvaluation = data.payload || data;
    enablePhase(6);
    setOutput("05",
      "✓ 风险评估完成\n" +
      `rating: ${data.overall_rating} (${data.overall_score.toFixed(1)})\n` +
      `decision: ${data.decision} | max_risk: ${data.max_risk_dimension} | pivots: ${data.pivot_count}`
    );
    renderSidebar(5);
  } else {
    setOutput("05", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});
bindPhaseAction(5, "get-risk", async () => {
  const { status, data } = await getJSON(`/api/v1/projects/${state.project_id}/risk/evaluation`);
  if (status === 200) {
    state.riskEvaluation = data.payload || data;
    setOutput("05", "RiskEvaluation:\n" + JSON.stringify(data.payload, null, 2).slice(0, 600));
    renderSidebar(5);
  } else {
    setOutput("05", "✗ HTTP " + status, "error");
  }
});

// Phase 06
bindPhaseAction(6, "work-package", async () => {
  const { status, data } = await postJSON(`/api/v1/projects/${state.project_id}/work_package/plan`);
  if (status === 200) {
    state.phase_status["06"] = true;
    state.workPackage = data.payload || data;
    enablePhase(7);
    setOutput("06",
      "✓ 工作包定稿\n" +
      `final_topic: ${data.final_topic}\n` +
      `from_pivot: ${data.from_pivot} | WPs: ${data.work_package_count} | ` +
      `experiments: ${data.experiment_count}`
    );
    renderSidebar(6);
  } else {
    setOutput("06", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});
bindPhaseAction(6, "get-work-package", async () => {
  const { status, data } = await getJSON(`/api/v1/projects/${state.project_id}/work_package/plan`);
  if (status === 200) {
    state.workPackage = data.payload || data;
    setOutput("06", "WorkPackagePlan:\n" + JSON.stringify(data.payload, null, 2).slice(0, 600));
    renderSidebar(6);
  } else {
    setOutput("06", "✗ HTTP " + status, "error");
  }
});

// Phase 07
bindPhaseAction(7, "proposal", async () => {
  const { status, data } = await postJSON(`/api/v1/projects/${state.project_id}/proposal/draft`);
  if (status === 200) {
    state.proposalDraft = data.payload || data;
    setOutput("07", "✓ 开题报告骨架生成\nsections: " + data.section_count + " | innovations: " + data.innovation_count);
    renderSidebar(7);
  } else {
    setOutput("07", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});
bindPhaseAction(7, "committee", async () => {
  const { status, data } = await postJSON(`/api/v1/projects/${state.project_id}/committee/review`);
  if (status === 200) {
    state.phase_status["07-committee"] = true;
    state.committeeReview = data.payload || data;
    enablePhase(8);
    setOutput("07",
      "✓ 委员会审查完成\n" +
      `verdict: ${data.overall_verdict} | maturity: ${data.proposal_maturity}\n` +
      `reviews: ${data.review_count} | questions: ${data.question_count} | discussion: ${(data.discussion || []).length}`
    );
    renderSidebar(7);
  } else {
    setOutput("07", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});

// Phase 08
bindPhaseAction(8, "final-package", async () => {
  const { status, data } = await postJSON(`/api/v1/projects/${state.project_id}/final_package/build`);
  if (status === 200) {
    state.finalPackage = data.payload || data;
    setOutput("08",
      "✓ 最终材料组装完成\n" +
      `ready_for_thesis: ${data.ready_for_thesis}\n` +
      `backend: ${data.backend_verification} | ui: ${data.ui_verification} | ` +
      `playwright: ${data.playwright_verification}\n` +
      `markdown: ${data.proposal_markdown_chars} chars`
    );
    renderSidebar(8);
  } else {
    setOutput("08", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});
bindPhaseAction(8, "export-md", async () => {
  const r = await fetch(API + `/api/v1/projects/${state.project_id}/final_package/markdown`);
  if (r.status === 200) {
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `proposal_${state.project_id}.md`;
    a.click();
    URL.revokeObjectURL(url);
    setOutput("08", "✓ Markdown 已下载: proposal_" + state.project_id + ".md");
  } else {
    setOutput("08", "✗ HTTP " + r.status, "error");
  }
});

// ------- 初始化 -------

document.getElementById("api-base").textContent = API;
setSidebar(0, "当前阶段：未启动", [], "");
