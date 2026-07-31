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
        { id: "literature", label: "文献检索", icon: "literature", count: () => (PA.model.papers || []).length },
        { id: "evidence", label: "Evidence", icon: "evidence", count: () => (PA.model.evidence || []).length },
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
    const productionPages = new Set(["projects", "literature", "evidence", "artifacts", "runs"]);
    if (PA.mode === "production" && !productionPages.has(id)) {
      container.append(PA.emptyState({
        title: "该页面尚未接入生产 API",
        text: "当前 MVP 仅开放 Projects、Papers、Evidence、Artifacts/Runs；不会显示 Demo 数据。",
      }));
    } else if (view && view.render) view.render(container, params);
    else container.append(PA.emptyState({ title: "页面不存在", text: `未找到视图 ${id}` }));
    document.querySelector(".app-main").scrollTop = 0;
  }

  function renderProjectSwitcher() {
    const sel = PA.clear(document.querySelector("#project-switcher"));
    for (const p of PA.model.projects || []) {
      sel.append(PA.h("option", { value: p.id, text: p.name }));
    }
    const known = (PA.model.projects || []).some((p) => p.id === PA.store.get("currentProject"));
    const first = (PA.model.projects || [])[0];
    if (!first) {
      sel.append(PA.h("option", { value: "", text: "暂无项目" }));
      sel.disabled = true;
      return;
    }
    sel.value = known ? PA.store.get("currentProject") : first.id;
    if (!known) PA.store.set("currentProject", first.id);
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

  document.addEventListener("DOMContentLoaded", async () => {
    if ("serviceWorker" in navigator && location.protocol.startsWith("http"))
      navigator.serviceWorker.register("/app/service-worker.js").catch(() => {});
    PA.store.applySettings();
    const viewRoot = root();
    viewRoot.append(PA.loadingState("正在连接 PaperAgent / PaperClaw…"));
    try {
      const boot = await PA.api.bootstrap();
      PA.mode = boot.mode;
      PA.model = boot.model;
      PA.data = boot.mode === "demo" ? boot.model : undefined;
      const badge = document.querySelector("#demo-badge");
      badge.hidden = boot.mode !== "demo";
      badge.title = boot.mode === "demo" ? "显式 Demo fixture（非真实论文）" : "";
      renderNav();
      renderProjectSwitcher();
      renderThemeToggle();
      bindCollapse();
      PA.navigate = navigate;
      window.addEventListener("hashchange", navigate);
      if (!location.hash) location.hash = "#/projects";
      navigate();
    } catch (error) {
      PA.mode = "failed";
      PA.model = { projects: [], papers: [], evidence: [], artifacts: [], runs: [] };
      PA.clear(viewRoot).append(PA.errorState(
        `${error.code || "startup_failed"}: ${error.message}`,
        () => location.reload(),
      ));
      document.querySelector("#demo-badge").hidden = true;
      return;
    }

    /* 启动流程：Splash → Gate（每会话一次，可在设置中关闭） */
    PA.onProjectChanged = () => {
      renderProjectSwitcher();
      renderNav();
      setActiveNav(currentRoute().id);
      navigate();
    };
    const INTRO_FLAG = "paperagent.intro.shown";
    if (PA.mode === "demo" && PA.store.settings().intro && !sessionStorage.getItem(INTRO_FLAG)) {
      sessionStorage.setItem(INTRO_FLAG, "1");
      PA.intro.start(() => PA.onProjectChanged());
    }
  });
})();
