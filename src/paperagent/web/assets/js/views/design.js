/* ==========================================================================
   Views · Design：Gap 与假设 / 方法设计 / 兼容性矩阵
   ========================================================================== */
"use strict";

(() => {
  const h = PA.h;
  const evById = (id) => PA.data.evidence.find((e) => e.id === id);
  const moduleById = (id) => PA.data.modules.find((m) => m.id === id);
  const baselineById = (id) => PA.data.baselines.find((b) => b.id === id);

  /* ================= Gap 与 Hypothesis ================= */
  PA.views.gap = {
    render(container) {
      const { gap, hypothesis } = PA.data.gapHypothesis;

      const gapPanel = h("section", { class: "panel" },
        h("div", { class: "panel-header" },
          h("div", {}, h("p", { class: "eyebrow", text: "RESEARCH GAP" }), h("h3", { text: "当前研究 Gap" })),
          h("span", { class: "badge badge-warning" }, h("span", { class: "dot" }), "已定位")),
        h("div", { class: "panel-body stack" },
          h("p", { style: "font-size:var(--pa-fs-16);line-height:1.7;font-weight:550", text: gap.statement }),
          h("div", {},
            h("p", { class: "eyebrow", text: "支持证据" }),
            h("div", { class: "stack", style: "gap:8px" },
              gap.supports.map((id) => {
                const ev = evById(id);
                return h("div", { class: "row", style: "align-items:flex-start;padding:8px 10px;border:1px solid var(--pa-line);border-radius:8px" },
                  h("span", { class: "mono small muted", style: "flex:none;padding-top:2px", text: id }),
                  h("span", { class: "small grow", text: ev.claim }),
                  PA.statusBadge(ev.status));
              }))),
          h("div", {},
            h("p", { class: "eyebrow", text: "限制条件" }),
            h("ul", { class: "small", style: "margin:4px 0;padding-left:18px;line-height:1.8" },
              gap.constraints.map((c) => h("li", { text: c })))),
          h("div", {},
            h("p", { class: "eyebrow", text: "原因分析" }),
            h("ol", { class: "small", style: "margin:4px 0;padding-left:18px;line-height:1.8" },
              gap.causeAnalysis.map((c) => h("li", { text: c }))))));

      const hypoPanel = h("section", { class: "panel" },
        h("div", { class: "panel-header" },
          h("div", {}, h("p", { class: "eyebrow", text: "FALSIFIABLE HYPOTHESIS" }), h("h3", { text: "可证伪假设" })),
          h("span", { class: "badge badge-primary" }, h("span", { class: "dot" }), "H1")),
        h("div", { class: "panel-body stack" },
          h("p", { style: "font-size:var(--pa-fs-16);line-height:1.7;font-weight:550", text: hypothesis.statement }),
          h("div", { class: "error-state", style: "border-color:var(--pa-info);background:var(--pa-info-soft);color:var(--pa-info)" },
            h("span", { html: PA.icon("info"), style: "display:flex;flex:none" }),
            h("div", {}, h("strong", { text: "证伪条件" }), h("div", { text: hypothesis.falsifiableBy }))),
          h("div", {},
            h("p", { class: "eyebrow", text: "目标指标" }),
            h("div", { class: "table-wrap" },
              h("table", { class: "table" },
                h("thead", {}, h("tr", {}, h("th", { text: "指标" }), h("th", { text: "目标" }))),
                h("tbody", {}, hypothesis.targetMetrics.map((m) =>
                  h("tr", {}, h("td", { text: m.name }), h("td", {}, h("span", { class: "mono", text: m.target })))))))),
          h("div", { class: "io-grid" },
            h("div", {},
              h("p", { class: "eyebrow", style: "color:var(--pa-danger)", text: "失败条件" }),
              h("ul", { class: "small", style: "margin:4px 0;padding-left:18px;line-height:1.8" },
                hypothesis.failureConditions.map((c) => h("li", { text: c })))),
            h("div", {},
              h("p", { class: "eyebrow", style: "color:var(--pa-warning)", text: "风险提示" }),
              h("ul", { class: "small", style: "margin:4px 0;padding-left:18px;line-height:1.8" },
                hypothesis.risks.map((c) => h("li", { text: c })))))));

      container.append(PA.demoBanner(),
        h("div", { class: "stack", style: "gap:var(--pa-sp-4)" }, gapPanel, hypoPanel));
    },
  };

  /* ================= 方法设计 ================= */
  PA.views.method = {
    render(container) {
      const plan = PA.data.methodPlan;
      const base = baselineById(plan.formula.baseline);
      const mods = plan.formula.modules.map(moduleById);

      /* ---- 公式条：A + B + C = Method ---- */
      const op = (s) => h("span", { class: "formula-op", text: s });
      const formula = h("section", { class: "panel" },
        h("div", { class: "panel-header" },
          h("div", {}, h("p", { class: "eyebrow", text: "METHOD FORMULA" }), h("h3", { text: "方法构成" })),
          h("span", { class: "badge badge-demo", text: `${plan.name} ${plan.version}` })),
        h("div", { class: "method-formula" },
          formulaNode("Baseline A", base.name, "零样本立体匹配主干", "is-baseline"),
          op("+"),
          formulaNode("Module B", mods[0].short, "代价体聚合段插入", "is-module"),
          op("+"),
          formulaNode("Module C", mods[1].short, "精炼段嵌入", "is-module"),
          op("="),
          formulaNode("Proposed", plan.name, plan.summary, "is-result")));

      function formulaNode(kind, name, desc, cls) {
        return h("div", { class: `formula-node ${cls}` },
          h("span", { class: "fn-kind", text: kind }),
          h("span", { class: "fn-name", text: name }),
          h("span", { class: "fn-desc clamp-3", text: desc }));
      }

      /* ---- SVG 流程图 ---- */
      const NODE_W = 148, NODE_H = 56, GAP_X = 42, LANE_Y = [26, 130];
      const flowSvg = buildFlow(plan.flow);
      function buildFlow(flow) {
        const cols = Math.max(...flow.nodes.map((n) => n.x)) + 1;
        const W = cols * (NODE_W + GAP_X) - GAP_X + 40;
        const H = 210;
        const pos = {};
        for (const n of flow.nodes) pos[n.id] = { x: 20 + n.x * (NODE_W + GAP_X), y: LANE_Y[n.lane] };

        const parts = [
          `<svg class="method-flow" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="方法流程图">`,
          `<defs><marker id="pa-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--pa-faint)"/></marker></defs>`,
          `<text class="flow-lane-label" x="20" y="14">主链路</text>`,
          `<text class="flow-lane-label" x="20" y="118">先验与内部信号</text>`,
        ];
        const center = (id) => ({ cx: pos[id].x + NODE_W / 2, cy: pos[id].y + NODE_H / 2 });
        for (const [a, b] of flow.edges) {
          const A = pos[a], B = pos[b];
          let d;
          if (A.y === B.y) {
            d = `M ${A.x + NODE_W} ${A.y + NODE_H / 2} L ${B.x} ${B.y + NODE_H / 2}`;
          } else {
            const ac = center(a), bc = center(b);
            d = `M ${ac.cx} ${A.y + NODE_H} C ${ac.cx} ${A.y + NODE_H + 34}, ${bc.cx} ${B.y - 34}, ${bc.cx} ${B.y}`;
          }
          parts.push(`<path class="flow-edge" d="${d}"/>`);
        }
        for (const n of flow.nodes) {
          const { x, y } = pos[n.id];
          parts.push(
            `<g><rect class="flow-box ${n.kind === "io" || n.kind === "output" ? "output" : n.kind}" x="${x}" y="${y}" width="${NODE_W}" height="${NODE_H}" rx="8"/>`,
            `<text class="flow-text" x="${x + NODE_W / 2}" y="${y + 24}" text-anchor="middle">${n.label}</text>`,
            `<text class="flow-sub" x="${x + NODE_W / 2}" y="${y + 41}" text-anchor="middle">${n.sub}</text></g>`);
        }
        parts.push("</svg>");
        return h("div", { class: "method-flow-wrap", html: parts.join("") });
      }

      const flowPanel = h("section", { class: "panel" },
        h("div", { class: "panel-header" },
          h("div", {}, h("p", { class: "eyebrow", text: "PIPELINE" }), h("h3", { text: "方法流程图" })),
          h("span", { class: "badge badge-outline", text: "SVG · 可横向滚动" })),
        flowSvg);

      /* ---- 模块卡片 ---- */
      const moduleCards = h("div", { class: "baseline-grid", style: "margin-bottom:0" });
      const baseCard = h("article", { class: "card baseline-card" },
        h("div", { class: "row-between" },
          h("h3", { text: `Baseline A · ${base.name}` }),
          h("span", { class: "badge badge-info", text: "主干" })),
        h("p", { class: "small muted", text: base.note }),
        h("dl", { class: "dl" },
          h("dt", { text: "输入" }), h("dd", { text: "校正双目图像对" }),
          h("dt", { text: "输出" }), h("dd", { text: "剪枝代价体 + 初始视差" }),
          h("dt", { text: "延迟" }), h("dd", { class: "mono", text: "92 ms" })));
      moduleCards.append(baseCard);
      for (const m of mods) {
        moduleCards.append(h("article", { class: "card baseline-card" },
          h("div", { class: "row-between" },
            h("h3", { text: m.name }),
            h("span", { class: "badge badge-warning", text: m.id === "mod-b" ? "聚合段" : "精炼段" })),
          h("p", { class: "small muted", text: m.motivation }),
          h("dl", { class: "dl" },
            h("dt", { text: "输入" }), h("dd", { text: m.input }),
            h("dt", { text: "输出" }), h("dd", { text: m.output }),
            h("dt", { text: "参数量" }), h("dd", { class: "mono", text: m.params }),
            h("dt", { text: "开销" }), h("dd", { class: "mono", text: m.overhead }),
            h("dt", { text: "依据" }), h("dd", {}, m.evidence.map((e) => h("span", { class: "chip", style: "margin-right:4px", text: e })))),
          h("div", {},
            h("p", { class: "eyebrow", style: "color:var(--pa-danger)", text: "风险" }),
            h("ul", { class: "small", style: "margin:4px 0;padding-left:18px" }, m.risks.map((r) => h("li", { text: r }))))));
      }
      const modulesPanel = h("section", { class: "panel" },
        h("div", { class: "panel-header" },
          h("div", {}, h("p", { class: "eyebrow", text: "COMPONENTS" }), h("h3", { text: "Baseline 与模块卡片" }))),
        h("div", { class: "panel-body" }, moduleCards));

      /* ---- Loss ---- */
      const lossPanel = h("section", { class: "panel" },
        h("div", { class: "panel-header" },
          h("div", {}, h("p", { class: "eyebrow", text: "OBJECTIVE" }), h("h3", { text: "损失函数" }))),
        h("div", { class: "panel-body stack" },
          h("p", { class: "mono small", style: "padding:10px 12px;background:var(--pa-bg-subtle);border-radius:8px",
            text: "L = 1.0·L_disp + 0.3·L_attn + 0.2·L_geom + 0.5·L_edge" }),
          h("div", { class: "table-wrap" },
            h("table", { class: "table" },
              h("thead", {}, h("tr", {}, h("th", { text: "项" }), h("th", { text: "定义" }), h("th", { class: "num", text: "权重" }), h("th", { text: "说明" }))),
              h("tbody", {}, plan.losses.map((l) => h("tr", {},
                h("td", { class: "mono", text: l.name }),
                h("td", { class: "mono small", text: l.def }),
                h("td", { class: "num mono", text: l.weight.toFixed(1) }),
                h("td", { class: "small muted", text: l.note }))))))));

      /* ---- Training Plan ---- */
      const trainPanel = h("section", { class: "panel" },
        h("div", { class: "panel-header" },
          h("div", {}, h("p", { class: "eyebrow", text: "TRAINING PLAN" }), h("h3", { text: "训练计划" }))),
        h("div", { class: "panel-body" },
          h("ul", { class: "timeline" },
            plan.trainingPlan.map((t, i) => h("li", {},
              h("span", { class: `tl-dot ${i === 0 ? "success" : i === 3 ? "active" : "info"}` }),
              h("div", { class: "row-between" },
                h("strong", { class: "small", text: t.phase }),
                h("span", { class: "mono small muted", text: t.steps })),
              h("p", { class: "small muted", text: t.detail }))))));

      /* ---- 预期与风险 ---- */
      const expectPanel = h("section", { class: "panel" },
        h("div", { class: "panel-header" },
          h("div", {}, h("p", { class: "eyebrow", text: "EXPECTED & RISKS" }), h("h3", { text: "预期效果与风险" }))),
        h("div", { class: "panel-body io-grid" },
          h("div", {},
            h("p", { class: "eyebrow", style: "color:var(--pa-success)", text: "预期效果" }),
            h("ul", { class: "io-list" }, plan.expected.map((e) => h("li", {}, h("span", { html: PA.icon("check"), style: "display:flex;color:var(--pa-success);flex:none;width:15px" }), h("span", { class: "small", text: e }))))),
          h("div", {},
            h("p", { class: "eyebrow", style: "color:var(--pa-danger)", text: "风险" }),
            h("ul", { class: "io-list" }, plan.risks.map((e) => h("li", {}, h("span", { html: PA.icon("warning"), style: "display:flex;color:var(--pa-warning);flex:none;width:15px" }), h("span", { class: "small", text: e })))))));

      /* ---- 最终 Method Plan 摘要 ---- */
      const finalPanel = h("section", { class: "panel" },
        h("div", { class: "panel-header" },
          h("div", {}, h("p", { class: "eyebrow", text: "FINAL PLAN" }), h("h3", { text: `Method Plan · ${plan.name}` })),
          h("div", { class: "row" },
            h("span", { class: "badge badge-warning" }, h("span", { class: "dot" }), "待质量门复检"),
            h("button", {
              class: "btn btn-secondary btn-sm", type: "button",
              onclick: () => PA.copyText(plan.summary, "Method Plan 摘要"),
            }, "复制摘要"),
            h("a", { class: "btn btn-primary btn-sm", href: "#/artifacts" }, "导出 Method Plan"))),
        h("div", { class: "panel-body" },
          h("p", { style: "line-height:1.7", text: plan.summary })));

      container.append(PA.demoBanner(),
        h("div", { class: "stack", style: "gap:var(--pa-sp-4)" },
          formula, flowPanel, modulesPanel,
          h("div", { class: "io-grid" }, lossPanel, trainPanel),
          expectPanel, finalPanel));
    },
  };

  /* ================= 兼容性矩阵 ================= */
  PA.views.matrix = {
    render(container) {
      const mx = PA.data.compatibility;
      const detailBox = h("div", { class: "matrix-detail" });

      const legend = h("div", { class: "matrix-legend", style: "margin-bottom:12px" },
        [["pass", "PASS"], ["warning", "WARNING"], ["fail", "FAIL"], ["unknown", "UNKNOWN"]].map(([k, label]) =>
          h("span", { class: "row" }, h("span", { class: `mx-cell mx-${k}`, style: "cursor:default;min-width:0", text: "●" }), label)),
        h("span", { class: "muted", style: "margin-left:auto", text: "点击单元格展开说明" }));

      const thead = h("thead", {}, h("tr", {},
        h("th", { text: "维度" }),
        mx.columns.map((c) => h("th", { text: c }))));

      const tbody = h("tbody");
      let failCount = 0, warnCount = 0;
      for (const dim of mx.dimensions) {
        const tr = h("tr", {}, h("th", { text: dim.label }));
        for (let col = 0; col < mx.columns.length; col++) {
          const cell = mx.cells[`${dim.id}|${col}`] || { s: "unknown", note: "未评估。" };
          if (cell.s === "fail") failCount++;
          if (cell.s === "warning") warnCount++;
          const btn = h("button", {
            class: `mx-cell mx-${cell.s}`, type: "button",
            "aria-label": `${dim.label} / ${mx.columns[col]}: ${cell.s.toUpperCase()}`,
            onclick: () => showDetail(dim, col, cell),
          }, cell.s.toUpperCase());
          tr.append(h("td", {}, btn));
        }
        tbody.append(tr);
      }

      function showDetail(dim, col, cell) {
        PA.clear(detailBox).append(
          h("section", { class: "panel panel-pad" },
            h("div", { class: "row-between" },
              h("div", { class: "row" },
                h("strong", { text: `${dim.label} × ${mx.columns[col]}` }),
                h("span", { class: `mx-cell mx-${cell.s}`, style: "cursor:default", text: cell.s.toUpperCase() })),
              h("button", { class: "icon-btn", type: "button", "aria-label": "关闭说明", html: PA.icon("x"), onclick: () => PA.clear(detailBox) })),
            h("p", { class: "small", style: "margin-top:8px;line-height:1.7", text: cell.note }),
            cell.s === "fail"
              ? h("p", { class: "small", style: "margin-top:6px;color:var(--pa-danger)", text: "阻塞项：需在质量门复检前修复。" })
              : null));
        detailBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }

      const summary = h("div", { class: "row wrap", style: "margin-bottom:12px" },
        h("span", { class: "badge badge-danger", text: `${failCount} FAIL` }),
        h("span", { class: "badge badge-warning", text: `${warnCount} WARNING` }),
        h("span", { class: "muted small", text: "维度：Shape / Meaning / Scale / Mask / Ordering / Gradient / Loss / License / Compute" }));

      container.append(PA.demoBanner(), summary, legend,
        h("div", { class: "matrix-wrap panel" },
          h("table", { class: "matrix-table" }, thead, tbody)),
        detailBox);
    },
  };
})();
