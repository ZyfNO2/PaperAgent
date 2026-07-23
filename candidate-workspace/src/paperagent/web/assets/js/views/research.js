/* ==========================================================================
   Views · Research：文献检索 / Evidence / Baseline
   ========================================================================== */
"use strict";

(() => {
  const h = PA.h;
  const paperById = (id) => PA.data.papers.find((p) => p.id === id);

  /* ================= 文献检索 ================= */
  PA.views.literature = {
    render(container) {
      const state = { q: "", source: "", year: "", verified: "", fav: false, sort: "rel", page: 1 };
      const perPage = () => PA.store.settings().pageSize;

      /* 左侧筛选 */
      const sourceSel = h("select", { class: "select", "aria-label": "数据源" },
        h("option", { value: "", text: "全部数据源" }),
        ["OpenAlex", "arXiv", "Crossref"].map((s) => h("option", { value: s, text: s })));
      sourceSel.addEventListener("change", () => { state.source = sourceSel.value; state.page = 1; draw(); });

      const yearSel = h("select", { class: "select", "aria-label": "时间范围" },
        h("option", { value: "", text: "全部年份" }),
        h("option", { value: "2024", text: "2024 至今" }),
        h("option", { value: "2022", text: "2022 至今" }),
        h("option", { value: "2020", text: "2020 至今" }),
        h("option", { value: "older", text: "2020 之前" }));
      yearSel.addEventListener("change", () => { state.year = yearSel.value; state.page = 1; draw(); });

      const verifiedSel = h("select", { class: "select", "aria-label": "验证状态" },
        h("option", { value: "", text: "全部状态" }),
        h("option", { value: "verified", text: "已验证" }),
        h("option", { value: "pending", text: "待审阅" }),
        h("option", { value: "rejected", text: "已拒绝" }));
      verifiedSel.addEventListener("change", () => { state.verified = verifiedSel.value; state.page = 1; draw(); });

      const favCb = h("input", { type: "checkbox", id: "fav-only" });
      favCb.addEventListener("change", () => { state.fav = favCb.checked; state.page = 1; draw(); });

      const filters = h("aside", { class: "panel lit-filters" },
        h("div", { class: "panel-header" }, h("h3", { text: "筛选" })),
        h("div", { class: "panel-body stack" },
          h("div", { class: "field" }, h("label", { text: "数据源" }), sourceSel),
          h("div", { class: "field" }, h("label", { text: "时间范围" }), yearSel),
          h("div", { class: "field" }, h("label", { text: "验证状态" }), verifiedSel),
          h("label", { class: "checkbox-label" }, favCb, "仅看收藏"),
          h("hr", { class: "divider" }),
          h("p", { class: "hint muted small", text: "数据源、关键词与检索结果均为 Demo 数据。" })));

      /* 顶部搜索 */
      const kwInput = h("input", { class: "input", type: "search", placeholder: "输入关键词，如 stereo matching · concrete · crack…", "aria-label": "关键词" });
      kwInput.addEventListener("input", () => { state.q = kwInput.value.trim().toLowerCase(); state.page = 1; draw(); });
      kwInput.addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });

      const sortSel = h("select", { class: "select", "aria-label": "排序" },
        h("option", { value: "rel", text: "按相关度" }),
        h("option", { value: "year-desc", text: "最新优先" }),
        h("option", { value: "year-asc", text: "最早优先" }));
      sortSel.addEventListener("change", () => { state.sort = sortSel.value; draw(); });

      const searchBtn = h("button", { class: "btn btn-primary", type: "button" },
        h("span", { html: PA.icon("search"), style: "display:flex;width:15px" }), "检索");
      searchBtn.addEventListener("click", doSearch);

      function doSearch() {
        searchBtn.disabled = true;
        searchBtn.lastChild.textContent = "检索中…";
        PA.clear(resultsBox).append(PA.loadingState("正在检索 OpenAlex / arXiv / Crossref（Demo）…"));
        setTimeout(() => {
          searchBtn.disabled = false;
          searchBtn.lastChild.textContent = "检索";
          state.page = 1;
          draw();
          PA.toast(`检索完成：${filtered().length} 条结果（Demo）`, "success");
        }, 650);
      }

      const toolbar = h("div", { class: "toolbar" },
        h("div", { class: "search-box grow", style: "max-width:none" }, h("span", { html: PA.icon("search") }), kwInput),
        sortSel, searchBtn);

      const resultsBox = h("div");
      const countLine = h("p", { class: "muted small", style: "margin-bottom:8px" });

      function filtered() {
        let list = PA.data.papers.filter((p) => {
          if (state.q && !`${p.title} ${p.authors} ${p.abstract} ${p.tags.join(" ")}`.toLowerCase().includes(state.q)) return false;
          if (state.source && p.source !== state.source) return false;
          if (state.verified && p.verified !== state.verified) return false;
          if (state.fav && !(PA.store.get("favorites") || {})[p.id] && !p.favorite) return false;
          if (state.year === "older" && p.year >= 2020) return false;
          else if (state.year && state.year !== "older" && p.year < Number(state.year)) return false;
          return true;
        });
        const by = {
          "rel": (a, b) => b.relevance - a.relevance,
          "year-desc": (a, b) => b.year - a.year,
          "year-asc": (a, b) => a.year - b.year,
        }[state.sort];
        return list.sort(by);
      }

      function draw() {
        PA.clear(resultsBox);
        const all = filtered();
        countLine.textContent = all.length
          ? `共 ${all.length} 篇文献 · 第 ${state.page} 页`
          : "";
        if (!all.length) {
          resultsBox.append(countLine, PA.emptyState({
            icon: "literature", title: "没有匹配的文献",
            text: "调整关键词或筛选条件后重新检索。",
          }));
          return;
        }
        const pages = Math.max(1, Math.ceil(all.length / perPage()));
        state.page = Math.min(state.page, pages);
        const items = all.slice((state.page - 1) * perPage(), state.page * perPage());
        const stack = h("div", { class: "paper-list-stack" });
        items.forEach((p) => stack.append(paperCard(p)));
        resultsBox.append(countLine, stack, pagination(pages));
      }

      function pagination(pages) {
        if (pages <= 1) return h("span");
        const box = h("div", { class: "pagination" });
        const prev = h("button", { class: "btn btn-sm btn-secondary", type: "button", disabled: state.page <= 1 }, "上一页");
        const next = h("button", { class: "btn btn-sm btn-secondary", type: "button", disabled: state.page >= pages }, "下一页");
        prev.addEventListener("click", () => { state.page--; draw(); });
        next.addEventListener("click", () => { state.page++; draw(); });
        box.append(prev, h("span", { text: `${state.page} / ${pages}` }), next);
        return box;
      }

      function paperCard(p) {
        const favs = PA.store.get("favorites") || {};
        const isFav = favs[p.id] !== undefined ? favs[p.id] : p.favorite;
        const favBtn = h("button", {
          class: `icon-btn ${isFav ? "active" : ""}`, type: "button",
          title: isFav ? "取消收藏" : "收藏",
          html: isFav ? PA.icon("starFill") : PA.icon("star"),
          "aria-pressed": String(isFav),
        });
        favBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          const f = PA.store.get("favorites") || {};
          f[p.id] = !isFav;
          PA.store.set("favorites", f);
          PA.toast(!isFav ? "已收藏" : "已取消收藏", "info", 1200);
          draw();
        });

        return h("article", { class: "card card-hover paper-card" },
          h("div", { class: "row-between", style: "align-items:flex-start" },
            h("div", { class: "grow", style: "min-width:0" },
              h("h3", { class: "paper-title", text: p.title }),
              h("p", { class: "paper-authors", text: `${p.authors} · ${p.year} · ${p.venue}` })),
            favBtn),
          h("p", { class: "paper-abstract clamp-3", text: p.abstract }),
          h("div", { class: "paper-foot" },
            PA.relBadge(p.relevance),
            PA.statusBadge(p.verified),
            h("span", { class: "chip", text: p.source }),
            p.tags.map((t) => h("span", { class: "chip", text: t })),
            h("span", { class: "toolbar-spacer" }),
            h("button", {
              class: "btn btn-sm btn-ghost", type: "button",
              onclick: () => openPaper(p),
            }, "详情")));
      }

      function openPaper(p) {
        PA.drawer({
          title: p.title,
          subtitle: `${p.authors} · ${p.year} · ${p.venue}`,
          body: h("div", { class: "stack" },
            h("div", { class: "row wrap" },
              PA.relBadge(p.relevance), PA.statusBadge(p.verified),
              h("span", { class: "chip", text: p.source })),
            h("div", {},
              h("p", { class: "eyebrow", text: "摘要" }),
              h("p", { class: "small", style: "line-height:1.7", text: p.abstract })),
            h("dl", { class: "dl" },
              h("dt", { text: "DOI" }), h("dd", { class: "mono", text: p.doi }),
              h("dt", { text: "数据源" }), h("dd", { text: p.source }),
              h("dt", { text: "标签" }), h("dd", {}, p.tags.map((t) => h("span", { class: "chip", style: "margin-right:4px", text: t })))),
            h("p", { class: "hint muted small", text: "Demo：未接入真实文献服务，无法跳转原文。" })),
          actions: [
            { label: "复制 DOI", onClick: () => { PA.copyText(p.doi, "DOI"); return true; } },
            { label: "关闭", kind: "primary" },
          ],
        });
      }

      container.append(
        PA.demoBanner(),
        h("div", { class: "lit-layout" }, filters,
          h("div", {}, toolbar, resultsBox)));
      draw();
    },
  };

  /* ================= Evidence ================= */
  PA.views.evidence = {
    render(container) {
      const state = { q: "", status: "", sort: "rel", view: "card" };
      const decisions = () => PA.store.get("evidenceDecisions") || {};
      const effStatus = (ev) => decisions()[ev.id] || ev.status;

      const kwInput = h("input", { class: "input", type: "search", placeholder: "搜索 Claim / 文献 / Evidence ID…", "aria-label": "搜索证据" });
      kwInput.addEventListener("input", () => { state.q = kwInput.value.trim().toLowerCase(); draw(); });

      const statusSel = h("select", { class: "select" },
        h("option", { value: "", text: "全部状态" }),
        h("option", { value: "verified", text: "已验证" }),
        h("option", { value: "pending", text: "待审阅" }),
        h("option", { value: "rejected", text: "已拒绝" }));
      statusSel.addEventListener("change", () => { state.status = statusSel.value; draw(); });

      const sortSel = h("select", { class: "select" },
        h("option", { value: "rel", text: "按相关度" }),
        h("option", { value: "id", text: "按 ID" }),
        h("option", { value: "status", text: "按状态" }));
      sortSel.addEventListener("change", () => { state.sort = sortSel.value; draw(); });

      const cardBtn = segBtn("grid", "卡片", "card");
      const tableBtn = segBtn("list", "表格", "table");
      const seg = h("div", { class: "segmented", role: "group", "aria-label": "视图切换" }, cardBtn, tableBtn);
      function segBtn(icon, label, val) {
        const b = h("button", { type: "button", "aria-pressed": String(state.view === val) },
          h("span", { html: PA.icon(icon), style: "display:flex" }), label);
        b.addEventListener("click", () => {
          state.view = val;
          cardBtn.setAttribute("aria-pressed", String(val === "card"));
          tableBtn.setAttribute("aria-pressed", String(val === "table"));
          draw();
        });
        return b;
      }

      const toolbar = h("div", { class: "toolbar" },
        h("div", { class: "search-box" }, h("span", { html: PA.icon("search") }), kwInput),
        statusSel, sortSel, h("span", { class: "toolbar-spacer" }), seg);

      const listBox = h("div");

      function filtered() {
        let list = PA.data.evidence.filter((ev) => {
          const paper = paperById(ev.paperId);
          if (state.q && !`${ev.id} ${ev.claim} ${paper.title}`.toLowerCase().includes(state.q)) return false;
          if (state.status && effStatus(ev) !== state.status) return false;
          return true;
        });
        const stOrder = { verified: 0, pending: 1, rejected: 2 };
        const by = {
          rel: (a, b) => b.relevance - a.relevance,
          id: (a, b) => a.id.localeCompare(b.id),
          status: (a, b) => stOrder[effStatus(a)] - stOrder[effStatus(b)],
        }[state.sort];
        return list.sort(by);
      }

      function setDecision(ev, status) {
        const d = decisions();
        d[ev.id] = status;
        PA.store.set("evidenceDecisions", d);
        PA.toast(`${ev.id} 已${status === "verified" ? "接受" : "拒绝"}（本地状态）`, status === "verified" ? "success" : "info", 1500);
        draw();
      }

      function actionButtons(ev, size = "btn-sm") {
        const cur = effStatus(ev);
        const accept = h("button", {
          class: `btn ${size} ${cur === "verified" ? "btn-primary" : "btn-secondary"}`, type: "button",
          disabled: cur === "verified",
        }, cur === "verified" ? "已接受" : "接受");
        accept.addEventListener("click", (e) => { e.stopPropagation(); setDecision(ev, "verified"); });
        const reject = h("button", {
          class: `btn ${size} ${cur === "rejected" ? "btn-danger" : "btn-secondary"}`, type: "button",
          disabled: cur === "rejected",
        }, cur === "rejected" ? "已拒绝" : "拒绝");
        reject.addEventListener("click", (e) => { e.stopPropagation(); setDecision(ev, "rejected"); });
        return [accept, reject];
      }

      function cardView(items) {
        const grid = h("div", { class: "evidence-grid" });
        for (const ev of items) {
          const paper = paperById(ev.paperId);
          grid.append(h("article", { class: "card card-hover evidence-card" },
            h("div", { class: "row-between" },
              h("span", { class: "mono small muted", text: ev.id }),
              PA.statusBadge(effStatus(ev))),
            h("p", { class: "claim", text: ev.claim }),
            h("div", { class: "small muted truncate", text: `📄 ${paper.title}`, title: paper.title }),
            h("div", { class: "row" }, PA.relBadge(ev.relevance), h("span", { class: "chip", text: ev.source.split("·")[0].trim() })),
            h("div", { class: "ev-actions" },
              ...actionButtons(ev),
              h("button", { class: "btn btn-sm btn-ghost", type: "button", style: "margin-left:auto", onclick: () => openDetail(ev) }, "详情"))));
        }
        return grid;
      }

      function tableView(items) {
        const rows = items.map((ev) => {
          const paper = paperById(ev.paperId);
          return h("tr", { class: "clickable", onclick: () => openDetail(ev) },
            h("td", { class: "mono", text: ev.id }),
            h("td", { style: "max-width:380px" }, h("div", { class: "clamp-2", text: ev.claim })),
            h("td", { style: "max-width:220px" }, h("div", { class: "truncate muted", text: paper.title, title: paper.title })),
            h("td", {}, PA.relBadge(ev.relevance)),
            h("td", {}, PA.statusBadge(effStatus(ev))),
            h("td", { onclick: (e) => e.stopPropagation() }, h("div", { class: "row" }, ...actionButtons(ev))));
        });
        return h("div", { class: "table-wrap" },
          h("table", { class: "table" },
            h("thead", {}, h("tr", {},
              h("th", { text: "ID" }), h("th", { text: "支持的 Claim" }), h("th", { text: "文献" }),
              h("th", { text: "相关度" }), h("th", { text: "状态" }), h("th", { text: "操作" }))),
            h("tbody", {}, rows)));
      }

      function openDetail(ev) {
        const paper = paperById(ev.paperId);
        PA.drawer({
          title: ev.id,
          subtitle: paper.title,
          body: h("div", { class: "stack" },
            h("div", { class: "row wrap" }, PA.statusBadge(effStatus(ev)), PA.relBadge(ev.relevance)),
            h("div", {},
              h("p", { class: "eyebrow", text: "支持的 Claim" }),
              h("p", { class: "claim", text: ev.claim })),
            h("div", {},
              h("p", { class: "eyebrow", text: "原文摘录" }),
              h("p", { class: "small", style: "line-height:1.7;font-style:italic", text: `“${ev.excerpt}”` })),
            h("dl", { class: "dl" },
              h("dt", { text: "来源" }), h("dd", { text: ev.source }),
              h("dt", { text: "文献" }), h("dd", { text: `${paper.title} (${paper.year})` }),
              h("dt", { text: "DOI" }), h("dd", { class: "mono", text: paper.doi }))),
          actions: [
            { label: "接受", kind: "primary", onClick: () => { setDecision(ev, "verified"); } },
            { label: "拒绝", kind: "danger", onClick: () => { setDecision(ev, "rejected"); } },
            { label: "关闭" },
          ],
        });
      }

      function draw() {
        PA.clear(listBox);
        const items = filtered();
        if (!items.length) {
          listBox.append(PA.emptyState({ icon: "evidence", title: "没有匹配的证据", text: "调整搜索或筛选条件。" }));
          return;
        }
        listBox.append(state.view === "card" ? cardView(items) : tableView(items));
      }

      container.append(PA.demoBanner(), toolbar, listBox);
      draw();
    },
  };

  /* ================= Baseline ================= */
  PA.views.baseline = {
    render(container) {
      const d = PA.data.baselines;

      /* 候选卡片 */
      const grid = h("div", { class: "baseline-grid" });
      for (const b of d) {
        const card = h("article", { class: `card baseline-card ${b.selected ? "selected" : ""}` },
          b.selected ? h("span", { class: "baseline-selected-ribbon", text: "SELECTED · Baseline A" }) : null,
          h("div", { class: "row-between" },
            h("h3", { text: b.name }),
            PA.stars(b.recommend)),
          h("dl", { class: "dl" },
            h("dt", { text: "论文" }), h("dd", { text: b.paper }),
            h("dt", { text: "代码" }), h("dd", { class: "mono small", text: b.code }),
            h("dt", { text: "许可证" }), h("dd", { text: b.codeLicense }),
            h("dt", { text: "数据集" }), h("dd", { text: b.datasets.join("、") })),
          h("div", { class: "row wrap" },
            Object.entries(b.metrics).map(([k, v]) =>
              h("span", { class: "chip" }, h("strong", { text: k + " " }), v))),
          h("div", { class: "row", style: "gap:16px" },
            h("span", { class: "small muted" }, "复现难度 ", PA.meter(b.difficulty)),
            h("span", { class: "small muted" }, "计算成本 ", PA.meter(b.cost, 5, "cost-meter"))),
          h("div", { class: "pros-cons" },
            h("div", {},
              h("p", { class: "eyebrow", style: "color:var(--pa-success)", text: "优点" }),
              h("ul", {}, b.pros.map((x) => h("li", { text: x })))),
            h("div", {},
              h("p", { class: "eyebrow", style: "color:var(--pa-danger)", text: "风险" }),
              h("ul", {}, b.risks.map((x) => h("li", { text: x }))))),
          h("p", { class: "compare-note", text: b.note }),
          h("div", { class: "row", style: "justify-content:flex-end" },
            b.selected
              ? h("span", { class: "badge badge-primary" }, h("span", { class: "dot" }), "当前选中")
              : h("button", {
                  class: "btn btn-sm btn-secondary", type: "button",
                  onclick: () => {
                    PA.modal({
                      title: "切换 Baseline（Demo）",
                      body: h("p", { text: `将 Baseline A 从 Fast-FoundationStereo 切换为 ${b.name}？Demo 模式仅更新页面显示。` }),
                      actions: [{ label: "取消" }, {
                        label: "确认切换", kind: "primary",
                        onClick: () => {
                          d.forEach((x) => (x.selected = x === b));
                          PA.toast(`已切换 Baseline A → ${b.name}（Demo）`, "success");
                          PA.views.baseline.render(PA.clear(document.querySelector("#view-root")));
                        },
                      }],
                    });
                  },
                }, "设为 Baseline A")));
        grid.append(card);
      }

      /* 对比表 */
      const metricKeys = ["EPE (px)", "Bad-2.0 (%)", "延迟 (ms)"];
      const cmp = h("section", { class: "panel" },
        h("div", { class: "panel-header" },
          h("div", {}, h("p", { class: "eyebrow", text: "COMPARISON" }), h("h3", { text: "候选对比表" })),
          h("span", { class: "badge badge-demo", text: "Demo 数据" })),
        h("div", { class: "table-wrap", style: "border:none;border-radius:0" },
          h("table", { class: "table" },
            h("thead", {}, h("tr", {},
              h("th", { text: "候选" }),
              metricKeys.map((k) => h("th", { class: "num", text: k })),
              h("th", { text: "复现难度" }), h("th", { text: "计算成本" }),
              h("th", { text: "推荐" }), h("th", { text: "状态" }))),
            h("tbody", {},
              d.map((b) => h("tr", { class: b.selected ? "" : "" },
                h("td", {}, h("strong", { text: b.name }), b.selected ? h("span", { class: "badge badge-primary", style: "margin-left:6px", text: "A" }) : null),
                metricKeys.map((k) => h("td", { class: "num mono", text: b.metrics[k] })),
                h("td", {}, PA.meter(b.difficulty)),
                h("td", {}, PA.meter(b.cost, 5, "cost-meter")),
                h("td", {}, PA.stars(b.recommend)),
                h("td", {}, b.selected ? PA.statusBadge("verified", "已选中") : PA.statusBadge("pending", "候选"))))))));

      container.append(PA.demoBanner(), grid, cmp);
    },
  };
})();
