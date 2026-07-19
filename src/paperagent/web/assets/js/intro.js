/* ==========================================================================
   Intro：开启动画（Splash）→ 选择工程 / 输入新题目（Gate）→ 进入工作台
   ========================================================================== */
"use strict";

(() => {
  const h = PA.h;

  const SPLASH_MS = 1750;

  PA.intro = {
    /** 启动流程入口；onDone() 在进入工作台后调用 */
    start(onDone) {
      const overlay = h("div", { class: "intro-overlay", role: "dialog", "aria-label": "启动 PaperAgent" });
      document.body.append(overlay);
      document.body.style.overflow = "hidden";

      let finished = false;
      const finish = (projectId) => {
        if (finished) return;
        finished = true;
        document.removeEventListener("keydown", onKey);
        if (projectId) PA.store.set("currentProject", projectId);
        overlay.classList.add("intro-out");
        document.body.style.overflow = "";
        setTimeout(() => overlay.remove(), PA.store.settings().motion ? 340 : 20);
        onDone && onDone();
      };

      const onKey = (e) => {
        if (e.key === "Escape") {
          if (overlay.querySelector(".intro-gate")) finish(PA.store.get("currentProject"));
          else showGate();
        }
      };
      document.addEventListener("keydown", onKey);

      /* ---------- Splash ---------- */
      const skipBtn = h("button", { class: "intro-skip", type: "button", onclick: () => showGate() }, "跳过 →");
      const splash = h("div", { class: "intro-splash" },
        h("div", { class: "intro-logo-mark", text: "P" }),
        h("div", { class: "intro-wordmark", text: "PaperAgent" }),
        h("div", { class: "intro-tag", text: "AI Research Workbench" }),
        h("div", { class: "intro-progress" }, h("div")));
      overlay.append(skipBtn, splash);

      const noMotion = !PA.store.settings().motion;
      const timer = setTimeout(() => showGate(), noMotion ? 250 : SPLASH_MS);

      function showGate() {
        clearTimeout(timer);
        if (finished) return;
        PA.clear(overlay);
        overlay.append(buildGate(finish));
      }
    },
  };

  /* ---------- Gate：选择工程 / 输入新题目 ---------- */
  function buildGate(finish) {
    let selectedId = PA.store.get("currentProject");

    /* 左栏：已有工程 */
    const projList = h("div", { class: "stack", style: "gap:8px" });
    const enterBtn = h("button", {
      class: "btn btn-primary", type: "button",
      onclick: () => finish(selectedId),
    }, "进入工作台 →");

    function drawProjects() {
      PA.clear(projList);
      for (const p of PA.data.projects) {
        const item = h("button", {
          class: `intro-proj ${p.id === selectedId ? "selected" : ""}`,
          type: "button",
          "aria-pressed": String(p.id === selectedId),
          onclick: () => {
            selectedId = p.id;
            drawProjects();
          },
        },
          h("span", { class: "ip-check", html: PA.icon("check") }),
          h("span", { class: "ip-main" },
            h("span", { class: "ip-name", text: p.name }),
            h("span", { class: "ip-meta", text: `${p.paperCount} 篇文献 · ${p.evidenceCount} 条证据 · 更新 ${p.updatedAt}` })),
          PA.stageBadge(p.stage));
        item.addEventListener("dblclick", () => finish(p.id));
        projList.append(item);
      }
    }
    drawProjects();

    const leftPane = h("section", { class: "intro-pane" },
      h("div", { class: "intro-pane-title", html: PA.icon("projects") }, h("span", { text: "选择已有工程" })),
      projList,
      h("p", { class: "hint faint small", text: "单击选择，双击直接进入。" }));

    /* 右栏：新题目 */
    const nameInput = h("input", { class: "input", type: "text", placeholder: "项目名称（可留空自动命名）", maxlength: "60" });
    const qInput = h("textarea", {
      class: "textarea", rows: 4, maxlength: "500",
      placeholder: "输入研究题目 / 研究问题，例如：\n隧道衬砌裂缝在衬砌渗水干扰下的三维量化精度如何提升？",
    });
    const createBtn = h("button", {
      class: "btn btn-primary btn-block", type: "button",
      onclick: () => {
        const q = qInput.value.trim();
        if (q.length < 3) {
          PA.toast("请输入研究题目（≥3 字）", "error");
          qInput.focus();
          return;
        }
        const name = nameInput.value.trim() || (q.length > 18 ? q.slice(0, 18) + "…" : q);
        const id = `proj-${Date.now().toString(36)}`;
        PA.data.projects.unshift({
          id, name, question: q,
          status: "active", stage: "contract",
          createdAt: "2026-07-20", updatedAt: "2026-07-20",
          paperCount: 0, evidenceCount: 0, verifiedEvidence: 0,
          baseline: null, methodPlan: null, gateStatus: "BLOCKED",
        });
        PA.toast(`已创建项目「${name}」（Demo）`, "success");
        finish(id);
      },
    }, "创建并进入 →");
    qInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) createBtn.click();
    });

    const rightPane = h("section", { class: "intro-pane" },
      h("div", { class: "intro-pane-title", html: PA.icon("plus") }, h("span", { text: "或输入新的研究题目" })),
      h("div", { class: "field" }, h("label", { text: "项目名称" }), nameInput),
      h("div", { class: "field grow" }, h("label", { text: "研究题目 / 问题" }), qInput,
        h("span", { class: "hint", text: "Ctrl+Enter 快速创建 · Demo 数据仅保留在内存中" })),
      createBtn);

    const gate = h("div", { class: "intro-gate" },
      h("div", { class: "intro-gate-head" },
        h("div", { class: "intro-mini-mark", text: "P" }),
        h("h1", { text: "开始你的研究" }),
        h("p", { text: "选择一个已有工程继续，或输入新的研究题目创建项目。" })),
      h("div", { class: "intro-gate-body" }, leftPane,
        h("div", { class: "stack" },
          h("div", { class: "intro-divider", text: "或" }),
          rightPane)),
      h("div", { class: "intro-gate-foot" },
        h("span", { class: "foot-note", text: "Demo 模式：全部数据为前端演示数据。" }),
        h("div", { class: "foot-actions" },
          h("button", { class: "btn btn-ghost", type: "button", onclick: () => finish(null) }, "暂不选择，先看看"),
          enterBtn)));
    return gate;
  }
})();
