/* ==========================================================================
   Views · Core：总览 / 项目 / 研究问题 / 设置
   ========================================================================== */
"use strict";

(() => {
  const h = PA.h;

  PA.proj = () =>
    PA.data.projects.find((p) => p.id === PA.store.get("currentProject")) || PA.data.projects[0];

  const stageIndex = (id) => PA.data.stages.findIndex((s) => s.id === id);

  /* ================= 总览 ================= */
  PA.views.overview = {
    render(container) {
      const p = PA.proj();
      const d = PA.data;
      const todoState = PA.store.get("todosDone") || {};

      /* Hero + 阶段进度 */
      const curIdx = stageIndex(p.stage);
      const stageTrack = h("div", { class: "stage-track", role: "list", "aria-label": "研究阶段" });
      d.stages.forEach((s, i) => {
        stageTrack.append(
          h("div", { class: `stage-step ${i < curIdx ? "done" : i === curIdx ? "current" : ""}`, role: "listitem" },
            h("span", { class: "stage-node", text: i < curIdx ? "✓" : String(i + 1) }),
            h("span", { class: "stage-label", text: s.label })));
        if (i < d.stages.length - 1)
          stageTrack.append(h("span", { class: `stage-line ${i < curIdx ? "done" : ""}` }));
      });

      const hero = h("section", { class: "panel overview-hero" },
        h("div", { class: "grow" },
          h("p", { class: "eyebrow", text: "当前研究项目" }),
          h("h2", { text: p.name }),
          h("p", { class: "muted clamp-2", style: "max-width:640px;margin-top:4px", text: p.question }),
          stageTrack),
        h("div", { class: "stack", style: "align-items:flex-end;flex:none" },
          PA.statusBadge(p.status),
          PA.stageBadge(p.stage),
          h("a", { class: "btn btn-primary btn-sm", href: "#/method" }, "继续方法设计")));

      /* 统计条 */
      const stats = h("div", { class: "stat-strip" },
        statCard(String(p.paperCount), "文献数量", "本项目的候选文献"),
        statCard(`${p.verifiedEvidence}/${p.evidenceCount}`, "已验证证据", "Evidence 通过人工确认"),
        statCard(p.baseline || "—", "Baseline", p.baseline ? "已完成选型" : "尚未选型", true),
        statCard(p.gateStatus, "Quality Gate", p.gateStatus === "REVISE" ? "存在阻塞项待修复" : "最新判定", true));

      /* 健康状态 */
      const gate = d.qualityGate;
      const health = h("section", { class: "panel" },
        h("div", { class: "panel-header" }, h("div", {}, h("p", { class: "eyebrow", text: "PIPELINE HEALTH" }), h("h3", { text: "关键状态" })),
          h("a", { class: "btn btn-ghost btn-sm", href: "#/gate" }, "查看质量门")),
        h("div", { class: "panel-body", style: "padding-top:8px;padding-bottom:8px" },
          healthRow("Baseline 状态", p.baseline ? ["badge-success", "已选定 · " + p.baseline] : ["badge-warning", "未选定"]),
          healthRow("Method Plan 状态", p.methodPlan ? ["badge-success", p.methodPlan] : ["badge-outline", "未生成"]),
          healthRow("兼容性矩阵", ["badge-danger", "1 项 FAIL（Mask 维度）"]),
          healthRow("Quality Gate", gate.verdict === "REVISE" ? ["badge-warning", "REVISE"] : ["badge-outline", gate.verdict]),
          healthRow("实验执行", ["badge-info", "1/7 Demo 完成，6 项 Planned"])));

      /* 最近任务 */
      const taskList = h("ul", { class: "mini-list" });
      for (const t of d.overview.recentTasks) {
        taskList.append(h("li", {},
          PA.statusBadge(t.status),
          h("div", { class: "mini-main" },
            h("div", { class: "mini-title", text: t.title }),
            h("div", { class: "mini-sub", text: `${t.at} · ${t.id}` })),
          h("a", { class: "icon-btn", href: "#/runs", title: "查看运行记录", html: PA.icon("chevronR") })));
      }
      const tasks = h("section", { class: "panel" },
        h("div", { class: "panel-header" }, h("div", {}, h("p", { class: "eyebrow", text: "RECENT TASKS" }), h("h3", { text: "最近任务" })),
          h("a", { class: "btn btn-ghost btn-sm", href: "#/runs" }, "全部")),
        h("div", { class: "panel-body", style: "padding-top:6px;padding-bottom:6px" }, taskList));

      /* 最近报告 */
      const repList = h("ul", { class: "mini-list" });
      for (const r of d.overview.recentReports) {
        repList.append(h("li", {},
          h("span", { class: "artifact-icon", text: r.kind === "bibtex" ? "BIB" : r.kind.toUpperCase().slice(0, 3) }),
          h("div", { class: "mini-main" },
            h("div", { class: "mini-title", text: r.name }),
            h("div", { class: "mini-sub", text: r.at })),
          h("a", { class: "icon-btn", href: "#/artifacts", title: "查看 Artifacts", html: PA.icon("chevronR") })));
      }
      const reports = h("section", { class: "panel" },
        h("div", { class: "panel-header" }, h("div", {}, h("p", { class: "eyebrow", text: "REPORTS" }), h("h3", { text: "最近生成的报告" })),
          h("a", { class: "btn btn-ghost btn-sm", href: "#/artifacts" }, "全部")),
        h("div", { class: "panel-body", style: "padding-top:6px;padding-bottom:6px" }, repList));

      /* 待办事项 */
      const todoList = h("ul", { class: "mini-list" });
      d.overview.todos.forEach((t) => {
        const done = t.done || todoState[t.id];
        const cb = h("input", { type: "checkbox", checked: done || null, "aria-label": t.text });
        cb.addEventListener("change", () => {
          const s = PA.store.get("todosDone") || {};
          s[t.id] = cb.checked;
          PA.store.set("todosDone", s);
          label.style.textDecoration = cb.checked ? "line-through" : "";
          label.style.color = cb.checked ? "var(--pa-faint)" : "";
          PA.toast(cb.checked ? "已标记完成" : "已恢复待办", "info", 1400);
        });
        const label = h("span", {
          class: "mini-title",
          text: t.text,
          style: done ? "text-decoration:line-through;color:var(--pa-faint)" : "",
        });
        todoList.append(h("li", {},
          h("label", { class: "checkbox-label grow", style: "align-items:flex-start" }, cb, label),
          h("span", { class: `badge ${t.priority === "high" ? "badge-danger" : t.priority === "mid" ? "badge-warning" : "badge-outline"}`, text: t.due })));
      });
      const todos = h("section", { class: "panel" },
        h("div", { class: "panel-header" }, h("div", {}, h("p", { class: "eyebrow", text: "TODO" }), h("h3", { text: "当前待办事项" }))),
        h("div", { class: "panel-body", style: "padding-top:6px;padding-bottom:6px" }, todoList));

      container.append(
        PA.store.settings().demo ? demoBanner() : h("span"),
        h("div", { class: "overview-grid" },
          hero, stats,
          h("div", { class: "col-8 stack" }, tasks, reports),
          h("div", { class: "col-4 stack" }, health, todos)));

      function statCard(value, label, foot, small = false) {
        return h("div", { class: "stat-card" },
          h("span", { class: "stat-value", text: value, style: small ? "font-size:var(--pa-fs-18)" : "" }),
          h("span", { class: "stat-label", text: label }),
          foot ? h("span", { class: "stat-foot", text: foot }) : null);
      }
      function healthRow(name, [cls, text]) {
        return h("div", { class: "health-row" },
          h("span", { class: "muted", text: name }),
          h("span", { class: `badge ${cls}` }, h("span", { class: "dot" }), text));
      }
    },
  };

  function demoBanner() {
    return h("div", { class: "demo-banner" },
      h("span", { html: PA.icon("info"), style: "display:flex;flex:none" }),
      h("span", { text: "Demo 模式：本工作台所有数据均为前端演示数据，不来自真实后端任务。可在 设置 中关闭此提示。" }),
      h("a", { class: "btn btn-ghost btn-sm", href: "#/settings", style: "margin-left:auto" }, "设置"));
  }
  PA.demoBanner = demoBanner;

  /* ================= 项目 ================= */
  PA.views.projects = {
    render(container) {
      const state = { q: "", status: "", stage: "" };
      const listWrap = h("div");

      const search = h("div", { class: "search-box" },
        h("span", { html: PA.icon("search") }),
        h("input", { class: "input", type: "search", placeholder: "搜索项目名称或研究问题…", "aria-label": "搜索项目" }));
      search.querySelector("input").addEventListener("input", (e) => { state.q = e.target.value.trim().toLowerCase(); draw(); });

      const statusSel = h("select", { class: "select", "aria-label": "按状态筛选" },
        h("option", { value: "", text: "全部状态" }),
        h("option", { value: "active", text: "进行中" }),
        h("option", { value: "paused", text: "已暂停" }));
      statusSel.addEventListener("change", () => { state.status = statusSel.value; draw(); });

      const stageSel = h("select", { class: "select", "aria-label": "按阶段筛选" },
        h("option", { value: "", text: "全部阶段" }),
        PA.data.stages.map((s) => h("option", { value: s.id, text: s.label })));
      stageSel.addEventListener("change", () => { state.stage = stageSel.value; draw(); });

      const toolbar = h("div", { class: "toolbar" },
        search, statusSel, stageSel,
        h("span", { class: "toolbar-spacer" }),
        h("button", { class: "btn btn-primary", type: "button", onclick: openCreate }, PA.h("span", { html: PA.icon("plus"), style: "display:flex;width:15px" }), "新建项目"));

      function filtered() {
        return PA.data.projects.filter((p) => {
          if (state.q && !`${p.name} ${p.question}`.toLowerCase().includes(state.q)) return false;
          if (state.status && p.status !== state.status) return false;
          if (state.stage && p.stage !== state.stage) return false;
          return true;
        });
      }

      function draw() {
        PA.clear(listWrap);
        const items = filtered();
        if (!items.length) {
          listWrap.append(PA.emptyState({
            title: "没有匹配的项目",
            text: state.q || state.status || state.stage ? "尝试调整搜索或筛选条件。" : "还没有项目，创建第一个研究项目开始工作。",
            actionLabel: "新建项目",
            onAction: openCreate,
          }));
          return;
        }
        const grid = h("div", { class: "project-grid" });
        for (const p of items) grid.append(projectCard(p));
        listWrap.append(grid);
      }

      function projectCard(p) {
        const isCurrent = p.id === PA.store.get("currentProject");
        return h("article", { class: `card card-hover project-card ${isCurrent ? "selected" : ""}` },
          h("div", { class: "row-between" },
            h("h3", { class: "truncate", text: p.name, style: "min-width:0" }),
            PA.statusBadge(p.status)),
          h("p", { class: "project-q clamp-2", text: p.question }),
          h("div", { class: "project-meta" },
            h("span", { text: `创建 ${p.createdAt}` }), h("span", { text: "·" }),
            h("span", { text: `更新 ${p.updatedAt}` }), h("span", { text: "·" }),
            h("span", { text: `${p.paperCount} 篇文献 / ${p.evidenceCount} 条证据` })),
          h("div", { class: "project-foot" },
            PA.stageBadge(p.stage),
            h("div", { class: "row" },
              isCurrent ? h("span", { class: "badge badge-primary", text: "当前" }) : null,
              h("button", {
                class: "btn btn-sm btn-primary", type: "button",
                onclick: () => {
                  PA.store.set("currentProject", p.id);
                  PA.toast(`已进入项目「${p.name}」`, "success");
                  setTimeout(() => { location.hash = "#/overview"; location.reload(); }, 250);
                },
              }, "进入项目"))));
      }

      function openCreate() {
        const name = h("input", { class: "input", type: "text", placeholder: "例如：隧道衬砌表观病害三维检测" });
        const question = h("textarea", { class: "textarea", rows: 3, placeholder: "用一句话描述可被证据检验的研究问题…" });
        const stage = h("select", { class: "select" }, PA.data.stages.map((s) => h("option", { value: s.id, text: s.label })));
        PA.modal({
          title: "新建研究项目（Demo）",
          body: h("div", { class: "stack" },
            h("div", { class: "field" }, h("label", { text: "项目名称" }), name),
            h("div", { class: "field" }, h("label", { text: "研究问题" }), question,
              h("span", { class: "hint", text: "Demo 模式：项目仅保存在浏览器内存中，刷新后消失。" })),
            h("div", { class: "field" }, h("label", { text: "初始阶段" }), stage)),
          actions: [
            { label: "取消" },
            {
              label: "创建项目", kind: "primary",
              onClick: () => {
                const v = name.value.trim();
                if (v.length < 2) { PA.toast("请填写项目名称（≥2 字）", "error"); return true; }
                PA.data.projects.unshift({
                  id: `proj-${Date.now().toString(36)}`,
                  name: v,
                  question: question.value.trim() || "（待补充研究问题）",
                  status: "active", stage: stage.value,
                  createdAt: "2026-07-20", updatedAt: "2026-07-20",
                  paperCount: 0, evidenceCount: 0, verifiedEvidence: 0,
                  baseline: null, methodPlan: null, gateStatus: "BLOCKED",
                });
                PA.toast(`项目「${v}」已创建（Demo，未持久化）`, "success");
                draw();
              },
            },
          ],
        });
      }

      container.append(demoBanner(), toolbar, listWrap);
      draw();
    },
  };

  /* ================= 研究问题 ================= */
  PA.views.research = {
    render(container) {
      const p = PA.proj();
      const gh = PA.data.gapHypothesis;

      const field = (label, value, opts = {}) =>
        h("div", { class: "field" },
          h("label", { text: label }),
          opts.textarea
            ? h("textarea", { class: "textarea", rows: opts.rows || 3, disabled: true }, value)
            : h("input", { class: "input", type: "text", value, disabled: true }),
          opts.hint ? h("span", { class: "hint", text: opts.hint }) : null);

      const form = h("section", { class: "panel" },
        h("div", { class: "panel-header" },
          h("div", {}, h("p", { class: "eyebrow", text: "RESEARCH CONTRACT" }), h("h3", { text: "研究契约（结构化）" })),
          h("div", { class: "row" },
            h("span", { class: "badge badge-demo", text: "Demo 只读" }),
            h("button", { class: "btn btn-secondary btn-sm", type: "button", disabled: true, title: "Demo 模式不可编辑" }, "编辑"))),
        h("div", { class: "panel-body stack" },
          field("研究背景",
            "混凝土结构表观裂缝是评估其服役状态的核心指标。现有三维重建管线在弱纹理混凝土表面的裂缝边缘带存在显著视差误差，导致宽度/深度量化不可靠（EV-001）。",
            { textarea: true, rows: 3 }),
          field("研究问题", p.question, { textarea: true, rows: 2 }),
          h("div", { class: "io-grid" },
            field("研究目标", "裂缝边缘带 EPE ↓ ≥18%，宽度误差 ≤ ±0.05 mm，推理延迟 ≤ 120 ms。"),
            field("预期贡献", "① 面向损伤量化的立体匹配方法；② 公开混凝土双目评测集与协议。")),
          field("限制条件", gh.gap.constraints.join("；"), { textarea: true, rows: 2 }),
          h("div", { class: "io-grid" },
            field("数据集", "Scene Flow（预训练）、Middlebury 2014、ETH3D、自建混凝土双目集（约 1.8k 对，5 折）"),
            field("评价指标", "EPE、Bad-2.0、边缘带 EPE（±5px）、裂缝宽度误差（mm）、延迟（ms）"))));

      /* 右侧摘要 */
      const summary = h("aside", { class: "panel rq-summary" },
        h("div", { class: "panel-header" }, h("h3", { text: "项目摘要" })),
        h("div", { class: "panel-body" },
          h("dl", { class: "dl" },
            h("dt", { text: "项目" }), h("dd", { text: p.name }),
            h("dt", { text: "状态" }), h("dd", {}, PA.statusBadge(p.status)),
            h("dt", { text: "当前阶段" }), h("dd", {}, PA.stageBadge(p.stage)),
            h("dt", { text: "创建时间" }), h("dd", { text: p.createdAt }),
            h("dt", { text: "最近更新" }), h("dd", { text: p.updatedAt }),
            h("dt", { text: "文献" }), h("dd", { text: `${p.paperCount} 篇` }),
            h("dt", { text: "证据" }), h("dd", { text: `${p.verifiedEvidence}/${p.evidenceCount} 已验证` }))),
        h("div", { class: "panel-footer" },
          h("a", { class: "btn btn-secondary btn-sm btn-block", href: "#/artifacts" }, "查看 Research Contract 文档")));

      container.append(demoBanner(), h("div", { class: "rq-layout" }, form, summary));
    },
  };

  /* ================= 设置 ================= */
  PA.views.settings = {
    render(container) {
      const s = PA.store.settings();

      const themeRow = h("div", { class: "setting-row" },
        h("div", { class: "setting-info" },
          h("div", { class: "setting-name", text: "主题 / 深色模式" }),
          h("div", { class: "setting-desc", text: "浅色为米白科研风，深色为低亮度控制台风。" })),
        h("div", { class: "theme-swatch" },
          swatch("light", "swatch-light", "浅色"),
          swatch("dark", "swatch-dark", "深色")));

      function swatch(value, cls, label) {
        const b = h("button", {
          class: cls, type: "button", title: label,
          "aria-pressed": String(s.theme === value),
        });
        b.addEventListener("click", () => {
          PA.store.setSetting("theme", value);
          PA.store.applySettings();
          container.querySelectorAll(".theme-swatch button").forEach((x) =>
            x.setAttribute("aria-pressed", String(x === b)));
          document.querySelector("#theme-toggle").innerHTML = PA.icon(value === "dark" ? "sun" : "moon");
          PA.toast(`已切换到${label}主题`, "success", 1500);
        });
        return b;
      }

      const densitySel = select("density", [["comfortable", "舒适"], ["compact", "紧凑"]], (v) => {
        PA.store.setSetting("density", v); PA.store.applySettings();
      });
      const langSel = select("lang", [["zh", "中文"], ["en", "English（演示）"]], (v) => {
        PA.store.setSetting("lang", v);
        PA.toast("语言设置已保存（演示：界面暂不切换）", "info");
      });
      const pageSizeSel = select("pageSize", [["8", "8 条/页"], ["10", "10 条/页"], ["20", "20 条/页"], ["50", "50 条/页"]], (v) => {
        PA.store.setSetting("pageSize", Number(v));
        PA.toast("每页数量已更新", "success", 1500);
      });

      function select(key, options, onChange) {
        const sel = h("select", { class: "select", style: "width:auto" },
          options.map(([v, label]) => h("option", { value: v, text: label, selected: String(s[key]) === v || null })));
        sel.addEventListener("change", () => onChange(sel.value));
        return sel;
      }

      function toggle(key, name, desc, onChange) {
        const input = h("input", { type: "checkbox", checked: s[key] || null });
        input.addEventListener("change", () => {
          PA.store.setSetting(key, input.checked);
          PA.store.applySettings();
          if (onChange) onChange(input.checked);
        });
        return h("div", { class: "setting-row" },
          h("div", { class: "setting-info" },
            h("div", { class: "setting-name", text: name }),
            h("div", { class: "setting-desc", text: desc })),
          h("label", { class: "switch" }, input, h("span", { class: "track" })));
      }

      const appearance = h("section", { class: "panel" },
        h("div", { class: "panel-header" }, h("div", {}, h("p", { class: "eyebrow", text: "APPEARANCE" }), h("h3", { text: "外观" }))),
        h("div", { class: "panel-body", style: "padding-top:8px;padding-bottom:8px" },
          themeRow,
          h("div", { class: "setting-row" },
            h("div", { class: "setting-info" },
              h("div", { class: "setting-name", text: "页面密度" }),
              h("div", { class: "setting-desc", text: "紧凑模式适合小屏或高密度信息浏览。" })),
            densitySel),
          toggle("motion", "动画", "关闭后禁用过渡与入场动画，减少视觉干扰。")));

      const general = h("section", { class: "panel" },
        h("div", { class: "panel-header" }, h("div", {}, h("p", { class: "eyebrow", text: "GENERAL" }), h("h3", { text: "通用" }))),
        h("div", { class: "panel-body", style: "padding-top:8px;padding-bottom:8px" },
          h("div", { class: "setting-row" },
            h("div", { class: "setting-info" },
              h("div", { class: "setting-name", text: "语言" }),
              h("div", { class: "setting-desc", text: "界面语言（English 为演示占位）。" })),
            langSel),
          h("div", { class: "setting-row" },
            h("div", { class: "setting-info" },
              h("div", { class: "setting-name", text: "每页数量" }),
              h("div", { class: "setting-desc", text: "文献、证据等列表的默认分页大小。" })),
            pageSizeSel),
          toggle("intro", "启动引导", "每次会话开始时显示开启动画与项目选择界面。", (on) => {
            if (on) sessionStorage.removeItem("paperagent.intro.shown");
          }),
          toggle("demo", "Demo 模式", "显示 DEMO 标识与演示数据提示横幅。")));

      const dangerZone = h("section", { class: "panel" },
        h("div", { class: "panel-header" }, h("div", {}, h("p", { class: "eyebrow", text: "LOCAL DATA" }), h("h3", { text: "本地数据" }))),
        h("div", { class: "panel-body stack" },
          h("p", { class: "muted small", text: "设置、收藏与证据评审状态仅保存在浏览器 localStorage，不涉及任何后端持久化。" }),
          h("div", { class: "row" },
            h("button", {
              class: "btn btn-danger", type: "button",
              onclick: () => {
                PA.modal({
                  title: "重置本地数据",
                  body: h("p", { text: "将清空设置、收藏、证据评审状态并恢复默认值。确定继续？" }),
                  actions: [{ label: "取消" }, {
                    label: "确认重置", kind: "danger",
                    onClick: () => { localStorage.removeItem("paperagent.workbench.v1"); location.reload(); },
                  }],
                });
              },
            }, "重置本地数据"))));

      container.append(
        h("div", { class: "settings-grid" },
          h("div", { class: "stack" }, appearance, general),
          h("div", { class: "stack" }, dangerZone)));
    },
  };
})();
