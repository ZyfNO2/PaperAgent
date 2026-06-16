// TopicPilot-CN MVP 静态前端逻辑
// 不使用任何前端框架, 直接 fetch + DOM 操作
// 状态机: project_id + 每 Phase 状态, 按上游依赖逐个解锁按钮

const API = "http://127.0.0.1:18181";
const state = {
  project_id: null,
  phase_status: {
    "01": false, "02": false, "03": false, "04": false,
    "05": false, "06": false, "07-proposal": false, "07-committee": false, "08": false,
  },
  blocked: false,
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
  // 阻断所有后续 phase
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
  // 把后端响应的关键字段拼成 1-3 行文本
  const lines = [];
  for (const k of keys) {
    if (obj[k] !== undefined) {
      const v = obj[k];
      lines.push(`${k}: ${typeof v === "object" ? JSON.stringify(v).slice(0, 80) : v}`);
    }
  }
  return lines.join(" | ");
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
    setOutput("01", "✓ Phase 01 建档成功\n" + summarize(data, ["id", "case_id"]) +
      "\nrating=" + data.payload.intake_rating);
    // 自动 validate
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

// ------- Phase 02-08: 通用按钮绑定 -------

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

// Phase 02: 题目拆解
bindPhaseAction(2, "decompose", async () => {
  const { status, data } = await postJSON(
    `/api/v1/projects/${state.project_id}/topic/decompose`,
    { prefer: "heuristic" }
  );
  if (status === 200) {
    state.phase_status["02"] = true;
    enablePhase(3);
    setOutput("02", "✓ 题目拆解完成\n" + summarize(data, ["decomposition_rating", "allow_proceed_to_phase03"]));
  } else {
    setOutput("02", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});
bindPhaseAction(2, "get-spec", async () => {
  const { status, data } = await getJSON(
    `/api/v1/projects/${state.project_id}/topic/spec`
  );
  if (status === 200) {
    setOutput("02", "TopicSpec:\n" + JSON.stringify(data.payload, null, 2).slice(0, 800));
  } else {
    setOutput("02", "✗ HTTP " + status, "error");
  }
});

// Phase 03: 检索计划
bindPhaseAction(3, "search-plan", async () => {
  const { status, data } = await postJSON(
    `/api/v1/projects/${state.project_id}/search/plan`
  );
  if (status === 200) {
    state.phase_status["03"] = true;
    enablePhase(4);
    setOutput("03", "✓ 检索计划生成\n" + summarize(data, ["maturity_rating", "allow_proceed_to_phase04"]));
  } else {
    setOutput("03", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});
bindPhaseAction(3, "get-plan", async () => {
  const { status, data } = await getJSON(
    `/api/v1/projects/${state.project_id}/search/plan`
  );
  if (status === 200) {
    const layers = data.payload.query_layers.length;
    const total = data.payload.query_layers.reduce((s, l) => s + l.queries.length, 0);
    setOutput("03", `检索计划: ${layers} 层, ${total} 个总检索词\n` +
      JSON.stringify(data.payload.query_layers.map(l => `${l.layer}: ${l.title}`), null, 2));
  } else {
    setOutput("03", "✗ HTTP " + status, "error");
  }
});

// Phase 04: 证据账本
bindPhaseAction(4, "evidence-build", async () => {
  const { status, data } = await postJSON(
    `/api/v1/projects/${state.project_id}/evidence/build`,
    { prefer: "heuristic" }
  );
  if (status === 200) {
    state.phase_status["04"] = true;
    enablePhase(5);
    setOutput("04",
      "✓ 证据账本生成\n" +
      `rating: ${data.evidence_rating}\n` +
      `papers: ${data.paper_count} | datasets: ${data.dataset_count} | ` +
      `baselines: ${data.baseline_count} | metrics: ${data.metric_count}`
    );
  } else {
    setOutput("04", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});
bindPhaseAction(4, "get-ledger", async () => {
  const { status, data } = await getJSON(
    `/api/v1/projects/${state.project_id}/evidence/ledger`
  );
  if (status === 200) {
    setOutput("04", "EvidenceLedger:\n" + JSON.stringify(data.payload, null, 2).slice(0, 800));
  } else {
    setOutput("04", "✗ HTTP " + status, "error");
  }
});

// Phase 05: 风险评分
bindPhaseAction(5, "risk-evaluate", async () => {
  const { status, data } = await postJSON(
    `/api/v1/projects/${state.project_id}/risk/evaluate`,
    { prefer: "heuristic" }
  );
  if (status === 200) {
    state.phase_status["05"] = true;
    enablePhase(6);
    setOutput("05",
      "✓ 风险评估完成\n" +
      `rating: ${data.overall_rating} (${data.overall_score.toFixed(1)})\n` +
      `decision: ${data.decision} | max_risk: ${data.max_risk_dimension} | pivots: ${data.pivot_count}`
    );
  } else {
    setOutput("05", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});
bindPhaseAction(5, "get-risk", async () => {
  const { status, data } = await getJSON(
    `/api/v1/projects/${state.project_id}/risk/evaluation`
  );
  if (status === 200) {
    setOutput("05", "RiskEvaluation:\n" + JSON.stringify(data.payload, null, 2).slice(0, 600));
  } else {
    setOutput("05", "✗ HTTP " + status, "error");
  }
});

// Phase 06: 工作包
bindPhaseAction(6, "work-package", async () => {
  const { status, data } = await postJSON(
    `/api/v1/projects/${state.project_id}/work_package/plan`
  );
  if (status === 200) {
    state.phase_status["06"] = true;
    enablePhase(7);
    setOutput("06",
      "✓ 工作包定稿\n" +
      `final_topic: ${data.final_topic}\n` +
      `from_pivot: ${data.from_pivot} | WPs: ${data.work_package_count} | ` +
      `experiments: ${data.experiment_count}`
    );
  } else {
    setOutput("06", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});
bindPhaseAction(6, "get-work-package", async () => {
  const { status, data } = await getJSON(
    `/api/v1/projects/${state.project_id}/work_package/plan`
  );
  if (status === 200) {
    setOutput("06", "WorkPackagePlan:\n" + JSON.stringify(data.payload, null, 2).slice(0, 600));
  } else {
    setOutput("06", "✗ HTTP " + status, "error");
  }
});

// Phase 07: 开题报告 + 委员会
bindPhaseAction(7, "proposal", async () => {
  const { status, data } = await postJSON(
    `/api/v1/projects/${state.project_id}/proposal/draft`
  );
  if (status === 200) {
    setOutput("07", "✓ 开题报告骨架生成\nsections: " + data.section_count + " | innovations: " + data.innovation_count);
  } else {
    setOutput("07", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});
bindPhaseAction(7, "committee", async () => {
  const { status, data } = await postJSON(
    `/api/v1/projects/${state.project_id}/committee/review`
  );
  if (status === 200) {
    state.phase_status["07-committee"] = true;
    enablePhase(8);
    setOutput("07",
      "✓ 委员会审查完成\n" +
      `verdict: ${data.overall_verdict} | maturity: ${data.proposal_maturity}\n` +
      `reviews: ${data.review_count} | questions: ${data.question_count}`
    );
  } else {
    setOutput("07", "✗ " + (typeof data === "string" ? data : JSON.stringify(data)), "error");
  }
});

// Phase 08: 最终材料
bindPhaseAction(8, "final-package", async () => {
  const { status, data } = await postJSON(
    `/api/v1/projects/${state.project_id}/final_package/build`
  );
  if (status === 200) {
    setOutput("08",
      "✓ 最终材料组装完成\n" +
      `ready_for_thesis: ${data.ready_for_thesis}\n` +
      `backend: ${data.backend_verification} | ui: ${data.ui_verification} | ` +
      `playwright: ${data.playwright_verification}\n` +
      `markdown: ${data.proposal_markdown_chars} chars`
    );
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
