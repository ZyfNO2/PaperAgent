/* ==========================================================================
   App Shell：hash 路由、左侧导航、顶栏、项目切换、主题切换
   ========================================================================== */
"use strict";

(() => {
  const NAV = [
    {
      section: "工作台",
      items: [
        { id: "overview", label: "总览", icon: "overview" },
        { id: "projects", label: "项目", icon: "projects" },
      ],
    },
    {
      section: "研究流程",
      items: [
        { id: "research", label: "研究问题", icon: "question" },
        { id: "literature", label: "文献检索", icon: "literature", count: () => PA.data.papers.length },
        { id: "evidence", label: "Evidence", icon: "evidence", count: () => PA.data.evidence.length },
        { id: "baseline", label: "Baseline", icon: "baseline" },
        { id: "gap", label: "Gap 与假设", icon: "gap" },
        { id: "method", label: "方法设计", icon: "method" },
      ],
    },
    {
      section: "验证与产出",
      items: [
        { id: "matrix", label: "兼容性矩阵", icon: "matrix" },
        { id: "experiments", label: "实验", icon: "experiment" },
        { id: "gate", label: "质量门", icon: "gate" },
        { id: "artifacts", label: "Artifacts", icon: "artifacts" },
        { id: "runs", label: "运行记录", icon: "runs" },
      ],
    },
    {
      section: "系统",
      items: [{ id: "settings", label: "设置", icon: "settings" }],
    },
  ];

  const TITLES = {
    overview: ["总览", "工作台 / 总览"],
    projects: ["项目", "工作台 / 项目"],
    research: ["研究问题", "研究流程 / 研究问题"],
    literature: ["文献检索", "研究流程 / 文献检索"],
    evidence: ["Evidence 证据", "研究流程 / Evidence"],
    baseline: ["Baseline 选型", "研究流程 / Baseline"],
    gap: ["Gap 与假设", "研究流程 / Gap 与 Hypothesis"],
    method: ["方法设计", "研究流程 / Method Design"],
    matrix: ["兼容性矩阵", "验证与产出 / Compatibility Matrix"],
    experiments: ["实验方案", "验证与产出 / Experiments"],
    gate: ["质量门", "验证与产出 / Quality Gate"],
    artifacts: ["Artifacts", "验证与产出 / Artifacts"],
    runs: ["运行记录", "验证与产出 / Runs"],
    settings: ["设置", "系统 / 设置"],
  };

  const root = () => document.querySelector("#view-root");

  function renderNav() {
    const scroll = PA.clear(document.querySelector("#nav-scroll"));
    const collapsed = PA.store.get("navCollapsed");
    document.querySelector("#app-shell").classList.toggle("nav-collapsed", collapsed);
    for (const section of NAV) {
      const sec = PA.h("div", { class: "nav-section" },
        PA.h("div", { class: "nav-section-title", text: section.section }));
      for (const item of section.items) {
        const count = item.count ? item.count() : null;
        sec.append(
          PA.h("a", {
            class: "nav-item",
            href: `#/${item.id}`,
            dataset: { nav: item.id },
            title: item.label,
          },
            PA.h("span", { html: PA.icon(item.icon), style: "display:flex;flex:none" }),
            PA.h("span", { class: "nav-label", text: item.label }),
            count != null ? PA.h("span", { class: "nav-count", text: String(count) }) : null));
      }
      scroll.append(sec);
    }
  }

  function setActiveNav(id) {
    document.querySelectorAll(".nav-item").forEach((el) => {
      el.classList.toggle("active", el.dataset.nav === id);
    });
  }

  function currentRoute() {
    const hash = location.hash.replace(/^#\/?/, "");
    const [id, query] = hash.split("?");
    return { id: TITLES[id] ? id : "overview", params: new URLSearchParams(query || "") };
  }

  function navigate() {
    const { id, params } = currentRoute();
    const view = PA.views[id];
    const [title, crumb] = TITLES[id];
    document.querySelector("#page-title").textContent = title;
    document.querySelector("#breadcrumb").textContent = crumb;
    setActiveNav(id);
    const container = root();
    PA.clear(container);
    container.classList.remove("view-enter");
    void container.offsetWidth; // 重启动画
    container.classList.add("view-enter");
    if (view && view.render) view.render(container, params);
    else container.append(PA.emptyState({ title: "页面不存在", text: `未找到视图 ${id}` }));
    document.querySelector(".app-main").scrollTop = 0;
  }

  function renderProjectSwitcher() {
    const sel = PA.clear(document.querySelector("#project-switcher"));
    for (const p of PA.data.projects) {
      sel.append(PA.h("option", { value: p.id, text: p.name }));
    }
    const known = PA.data.projects.some((p) => p.id === PA.store.get("currentProject"));
    sel.value = known ? PA.store.get("currentProject") : PA.data.projects[0].id;
    sel.addEventListener("change", () => {
      PA.store.set("currentProject", sel.value);
      PA.toast(`已切换到项目「${sel.selectedOptions[0].text}」`, "info");
      navigate();
    });
  }

  function renderThemeToggle() {
    const btn = document.querySelector("#theme-toggle");
    const sync = () => {
      btn.innerHTML = PA.icon(PA.store.settings().theme === "dark" ? "sun" : "moon");
      btn.setAttribute("aria-label", PA.store.settings().theme === "dark" ? "切换到浅色" : "切换到深色");
    };
    btn.addEventListener("click", () => {
      const next = PA.store.settings().theme === "dark" ? "light" : "dark";
      PA.store.setSetting("theme", next);
      PA.store.applySettings();
      sync();
    });
    sync();
  }

  function bindCollapse() {
    const btn = document.querySelector("#nav-collapse-btn");
    const syncLabel = () => {
      btn.querySelector("span[aria-hidden]").textContent = PA.store.get("navCollapsed") ? "⇥" : "⇤";
    };
    btn.addEventListener("click", () => {
      PA.store.set("navCollapsed", !PA.store.get("navCollapsed"));
      renderNav();
      setActiveNav(currentRoute().id);
      syncLabel();
    });
    syncLabel();
  }

  document.addEventListener("DOMContentLoaded", () => {
    if ("serviceWorker" in navigator && location.protocol.startsWith("http"))
      navigator.serviceWorker.register("/app/service-worker.js").catch(() => {});
    PA.store.applySettings();
    renderNav();
    renderProjectSwitcher();
    renderThemeToggle();
    bindCollapse();
    window.addEventListener("hashchange", navigate);
    if (!location.hash) location.hash = "#/overview";
    navigate();
  });
})();
