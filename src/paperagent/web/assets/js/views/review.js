/* ==========================================================================
   Views · Review：实验 / 质量门 / Artifacts / 运行记录
   ========================================================================== */
"use strict";

(() => {
  const h = PA.h;

  /* ================= 实验 ================= */
  PA.views.experiments = {
    render(container) {
      const list = PA.data.experiments;

      const grid = h("div", { class: "exp-grid" });
      for (const e of list) {
        const statusBadge = e.status === "demo"
          ? h("span", { class: "badge badge-info" }, h("span", { class: "dot" }), "Demo 结果")
          : h("span", { class: "badge badge-outline" }, h("span", { class: "dot" }), "Planned");

        const resultsBlock = e.results
          ? h("div", {},
              h("p", { class: "eyebrow", text: "结果（Demo）" }),
              h("div", { class: "row wrap" },
                Object.entries(e.results).map(([k, v]) =>
                  h("span", { class: "chip" }, h("strong", { text: k + " " }), h("span", { class: "mono", text: v })))))
          : h("p", { class: "small faint", text: "尚未执行 — 所有未来结果仅存在于计划中。" });

        grid.append(h("article", { class: "card exp-card" },
          h("div", { class: "row-between" },
            h("span", { class: "exp-kind", style: `color:${kindColor(e.kind)}`, text: e.kind }),
            statusBadge),
          h("div", {},
            h("h3", { text: e.id }),
            h("p", { class: "small muted", text: e.config })),
          h("dl", { class: "dl" },
            h("dt", { text: "Dataset" }), h("dd", { class: "small", text: e.dataset }),
            h("dt", { text: "Metric" }), h("dd", { class: "small", text: e.metric }),
            h("dt", { text: "Seed" }), h("dd", { class: "mono small", text: String(e.seed) }),
            h("dt", { text: "Compute" }), h("dd", { class: "mono small", text: e.compute })),
          h("div", { class: "exp-expected" },
            h("strong", { class: "small", text: "预期结果：" }),
            h("span", { class: "small", text: e.expected })),
          resultsBlock,
          h("p", { class: "small", style: "color:var(--pa-warning)" }, "风险：" + e.risk)));
      }

      function kindColor(kind) {
        if (kind.startsWith("Baseline")) return "var(--pa-info)";
        if (kind.startsWith("Full")) return "var(--pa-primary)";
        if (kind.startsWith("Negative")) return "var(--pa-danger)";
        if (kind.startsWith("Ablation")) return "var(--pa-accent)";
        if (kind.startsWith("Interaction")) return "var(--pa-accent)";
        return "var(--pa-warning)";
      }

      const note = h("div", { class: "demo-banner" },
        h("span", { html: PA.icon("info"), style: "display:flex;flex:none" }),
        h("span", { text: "除 EXP-01 标注为 Demo 结果外，其余实验均为 Planned —— 此处不展示任何伪装成真实执行的实验数据。" }));

      container.append(PA.demoBanner(), note, grid);
    },
  };

  /* ================= 质量门 ================= */
  PA.views.gate = {
    render(container) {
      const g = PA.data.qualityGate;
      const verdictCls = { GO: "verdict-go", REVISE: "verdict-revise", "NO-GO": "verdict-nogo", BLOCKED: "verdict-blocked" }[g.verdict];

      const verdict = h("section", { class: "panel gate-verdict" },
        h("div", { class: `verdict-mark ${verdictCls}`, text: g.verdict }),
        h("div", { class: "grow" },
          h("p", { class: "eyebrow", text: "QUALITY GATE DECISION" }),
          h("h2", { text: "最终判定：" + g.verdict }),
          h("p", { class: "muted", style: "margin-top:4px;max-width:640px", text: g.summary }),
          h("p", { class: "faint small", style: "margin-top:6px", text: `${g.decidedAt} · ${g.decidedBy}` })),
        h("div", { class: "stack", style: "flex:none" },
          h("a", { class: "btn btn-secondary btn-sm", href: "#/artifacts" }, "查看 Audit Report"),
          h("button", {
            class: "btn btn-primary btn-sm", type: "button",
            onclick: () => PA.toast("复检任务已加入队列（Demo）", "info"),
          }, "触发复检")));

      const iconFor = { pass: "check", warning: "warning", fail: "x", unknown: "info" };
      const checkList = h("ul", { class: "mini-list", style: "padding:0 var(--pa-sp-5)" });
      for (const c of g.checks) {
        checkList.append(h("li", { class: "gate-item", style: "padding-left:0;padding-right:0" },
          h("span", { class: `gate-icon ${c.status}`, html: PA.icon(iconFor[c.status]) }),
          h("div", { class: "grow" },
            h("div", { class: "gate-name", text: c.name }),
            h("div", { class: "gate-note", text: c.note })),
          PA.statusBadge(c.status)));
      }
      const checksPanel = h("section", { class: "panel" },
        h("div", { class: "panel-header" },
          h("div", {}, h("p", { class: "eyebrow", text: "CHECKLIST" }), h("h3", { text: "检查项明细（8 项）" })),
          h("span", { class: "badge badge-demo", text: "Demo 数据" })),
        checkList);

      container.append(PA.demoBanner(), h("div", { class: "stack", style: "gap:var(--pa-sp-4)" }, verdict, checksPanel));
    },
  };

  /* ================= Artifacts ================= */
  PA.views.artifacts = {
    render(container) {
      const state = { type: "" };
      const listBox = h("div");

      const typeSel = h("select", { class: "select", "aria-label": "类型筛选" },
        h("option", { value: "", text: "全部类型" }),
        h("option", { value: "markdown", text: "Markdown" }),
        h("option", { value: "json", text: "JSON" }),
        h("option", { value: "bibtex", text: "BibTeX" }));
      typeSel.addEventListener("change", () => { state.type = typeSel.value; draw(); });

      const toolbar = h("div", { class: "toolbar" },
        h("span", { class: "muted small", text: `共 ${PA.data.artifacts.length} 个产物` }),
        h("span", { class: "toolbar-spacer" }), typeSel);

      const typeLabel = { markdown: "MD", json: "JSON", bibtex: "BIB" };
      const fileExt = { markdown: "md", json: "json", bibtex: "bib" };
      const mime = { markdown: "text/markdown", json: "application/json", bibtex: "text/plain" };

      function draw() {
        PA.clear(listBox);
        const items = PA.data.artifacts.filter((a) => !state.type || a.type === state.type);
        if (!items.length) {
          listBox.append(PA.emptyState({ icon: "artifacts", title: "没有该类型的产物", text: "切换类型筛选查看其他 Artifacts。" }));
          return;
        }
        const list = h("div", { class: "artifact-list" });
        for (const a of items) {
          list.append(h("div", { class: "artifact-row" },
            h("span", { class: "artifact-icon", text: typeLabel[a.type] }),
            h("div", { class: "artifact-main" },
              h("div", { class: "artifact-name", text: a.name }),
              h("div", { class: "artifact-meta", text: `${a.version} · 更新 ${a.updatedAt} · ${a.size}` })),
            h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => preview(a) },
              h("span", { html: PA.icon("eye"), style: "display:flex;width:15px" }), "预览"),
            h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => PA.copyText(a.preview, a.name) },
              h("span", { html: PA.icon("copy"), style: "display:flex;width:15px" }), "复制"),
            h("button", {
              class: "btn btn-sm btn-secondary", type: "button",
              onclick: () => PA.mockDownload(`${a.id}.${fileExt[a.type]}`, a.preview, mime[a.type]),
            }, h("span", { html: PA.icon("download"), style: "display:flex;width:15px" }), "下载")));
        }
        listBox.append(list);
      }

      function preview(a) {
        PA.modal({
          title: `${a.name} · 预览`,
          wide: true,
          body: h("div", { class: "stack" },
            h("div", { class: "row wrap" },
              h("span", { class: "chip", text: a.type }),
              h("span", { class: "chip", text: a.version }),
              h("span", { class: "chip", text: a.size }),
              h("span", { class: "badge badge-demo", text: "Demo 内容" })),
            h("pre", { class: "artifact-preview", text: a.preview })),
          actions: [
            { label: "复制全文", onClick: () => { PA.copyText(a.preview, a.name); return true; } },
            { label: "下载", kind: "primary", onClick: () => { PA.mockDownload(`${a.id}.${fileExt[a.type]}`, a.preview, mime[a.type]); return true; } },
            { label: "关闭" },
          ],
        });
      }

      container.append(PA.demoBanner(), toolbar, listBox);
      draw();
    },
  };

  /* ================= 运行记录 ================= */
  PA.views.runs = {
    render(container) {
      const listBox = h("div", { class: "stack", style: "gap:var(--pa-sp-3)" });

      for (const r of PA.data.runs) {
        const isRunning = r.status === "running";
        const toggle = h("button", { class: "btn btn-sm btn-ghost", type: "button" }, "日志");
        const logBox = h("pre", { class: "run-log hidden", text: r.log });
        toggle.addEventListener("click", () => {
          logBox.classList.toggle("hidden");
          toggle.textContent = logBox.classList.contains("hidden") ? "日志" : "收起";
        });

        listBox.append(h("section", { class: "panel" },
          h("div", { class: "panel-body", style: "padding:14px var(--pa-sp-5)" },
            h("div", { class: "row wrap" },
              isRunning
                ? h("span", { class: "spinner", style: "width:14px;height:14px;border-width:2px" })
                : PA.statusBadge(r.status),
              h("div", { class: "grow", style: "min-width:0" },
                h("div", { class: "row" },
                  h("strong", { class: "truncate", text: r.title }),
                  isRunning ? PA.statusBadge("running") : null),
                h("div", { class: "mini-sub muted small", text: `${r.startedAt} · 耗时 ${r.duration} · ${r.id}` })),
              PA.stageBadge(r.stage),
              toggle)),
          logBox));
      }

      container.append(PA.demoBanner(), listBox);
    },
  };
})();
