/* ==========================================================================
   UI 基础库：图标、DOM 助手、Toast、Modal、Drawer、状态组件、本地 store
   ========================================================================== */
"use strict";

window.PA = window.PA || {};

/* ---------- SVG 图标（stroke 风格，1.7px） ---------- */
PA.icons = (() => {
  const wrap = (paths) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
  return {
    overview: wrap('<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>'),
    projects: wrap('<path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'),
    question: wrap('<circle cx="12" cy="12" r="9"/><path d="M9.2 9a2.9 2.9 0 0 1 5.6 1c0 1.8-2.5 2.2-2.8 3.8"/><circle cx="12" cy="17.2" r="0.4" fill="currentColor"/>'),
    literature: wrap('<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5V5.5"/><path d="M8 7.5h8M8 11h5"/>'),
    evidence: wrap('<path d="M9 3h6v4l4.5 9.5A2.4 2.4 0 0 1 17.4 20H6.6a2.4 2.4 0 0 1-2.1-3.5L9 7z"/><path d="M7.5 14h9"/>'),
    baseline: wrap('<path d="M4 20V6"/><path d="M4 20h16"/><path d="M8 16v-5M12 16V8M16 16v-3M20 16V5"/>'),
    gap: wrap('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/><path d="M8.5 11h5"/>'),
    method: wrap('<rect x="3" y="9" width="6" height="6" rx="1.5"/><rect x="15" y="3" width="6" height="6" rx="1.5"/><rect x="15" y="15" width="6" height="6" rx="1.5"/><path d="M9 12h3.5m0 0L11 10.5M12.5 12 11 13.5M15 6h-2.5M15 18h-2.5"/>'),
    matrix: wrap('<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>'),
    experiment: wrap('<path d="M10 3v6.5L4.8 18.6A2 2 0 0 0 6.6 21.5h10.8a2 2 0 0 0 1.8-2.9L14 9.5V3"/><path d="M8 3h8"/><path d="M7 15h10"/>'),
    gate: wrap('<path d="M12 3l7 3v5.5c0 4.5-3 7.8-7 9.5-4-1.7-7-5-7-9.5V6z"/><path d="m9 12 2 2 4-4.5"/>'),
    artifacts: wrap('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/>'),
    runs: wrap('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/>'),
    settings: wrap('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .32 1.76l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.6 1.6 0 0 0-1.76-.32 1.6 1.6 0 0 0-1 1.48V21a2 2 0 1 1-4 0v-.09a1.6 1.6 0 0 0-1-1.48 1.6 1.6 0 0 0-1.76.32l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.6 1.6 0 0 0 4.6 15a1.6 1.6 0 0 0-1.48-1H3a2 2 0 1 1 0-4h.09a1.6 1.6 0 0 0 1.48-1 1.6 1.6 0 0 0-.32-1.76l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.6 1.6 0 0 0 1.76.32h.01a1.6 1.6 0 0 0 1-1.48V3a2 2 0 1 1 4 0v.09a1.6 1.6 0 0 0 1 1.48 1.6 1.6 0 0 0 1.76-.32l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.6 1.6 0 0 0-.32 1.76v.01a1.6 1.6 0 0 0 1.48 1H21a2 2 0 1 1 0 4h-.09a1.6 1.6 0 0 0-1.48 1z"/>'),
    search: wrap('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>'),
    star: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m12 3 2.7 5.6 6.1.8-4.5 4.3 1.1 6-5.4-2.9-5.4 2.9 1.1-6L3.2 9.4l6.1-.8z"/></svg>',
    starFill: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m12 3 2.7 5.6 6.1.8-4.5 4.3 1.1 6-5.4-2.9-5.4 2.9 1.1-6L3.2 9.4l6.1-.8z"/></svg>',
    check: wrap('<path d="m4.5 12.5 5 5 10-11"/>'),
    x: wrap('<path d="M6 6l12 12M18 6 6 18"/>'),
    plus: wrap('<path d="M12 5v14M5 12h14"/>'),
    chevronR: wrap('<path d="m9 5 7 7-7 7"/>'),
    chevronD: wrap('<path d="m5 9 7 7 7-7"/>'),
    download: wrap('<path d="M12 3v12m0 0 4.5-4.5M12 15l-4.5-4.5"/><path d="M4 19h16"/>'),
    copy: wrap('<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>'),
    eye: wrap('<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>'),
    filter: wrap('<path d="M4 5h16l-6.2 7.2v6L10 20v-7.8z"/>'),
    sun: wrap('<circle cx="12" cy="12" r="4"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/>'),
    moon: wrap('<path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/>'),
    warning: wrap('<path d="M12 4 2.8 20h18.4z"/><path d="M12 10v4.5"/><circle cx="12" cy="17.4" r="0.4" fill="currentColor"/>'),
    info: wrap('<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><circle cx="12" cy="7.8" r="0.4" fill="currentColor"/>'),
    clock: wrap('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
    empty: wrap('<path d="M4 8c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z"/><path d="M4 8v8c0 1.7 3.6 3 8 3s8-1.3 8-3V8"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>'),
    sort: wrap('<path d="M8 6v12m0 0-3-3m3 3 3-3"/><path d="M16 18V6m0 0-3 3m3-3 3 3"/>'),
    external: wrap('<path d="M14 4h6v6"/><path d="M20 4 11 13"/><path d="M19 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5"/>'),
    list: wrap('<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="0.5" fill="currentColor"/><circle cx="4.5" cy="12" r="0.5" fill="currentColor"/><circle cx="4.5" cy="18" r="0.5" fill="currentColor"/>'),
    grid: wrap('<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>'),
  };
})();

PA.icon = (name) => PA.icons[name] || PA.icons.info;

/* ---------- DOM 助手 ---------- */
PA.h = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "html") node.innerHTML = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on") && typeof value === "function")
      node.addEventListener(key.slice(2), value);
    else if (key === "dataset") Object.assign(node.dataset, value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
};

PA.clear = (node) => {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
};

/* ---------- Toast ---------- */
PA.toast = (message, kind = "info", ms = 2600) => {
  const root = document.querySelector("#toast-root");
  const el = PA.h("div", { class: `toast toast-${kind}`, role: "status" },
    PA.h("span", { class: "dot" }), PA.h("span", { text: message }));
  root.append(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity 200ms";
    setTimeout(() => el.remove(), 220);
  }, ms);
};

/* ---------- Modal ---------- */
PA.modal = ({ title, body, actions = [], wide = false }) => {
  const root = document.querySelector("#modal-root");
  const close = () => backdrop.remove();
  const footer = actions.length
    ? PA.h("div", { class: "modal-footer" },
        actions.map((a) =>
          PA.h("button", {
            class: `btn ${a.kind ? `btn-${a.kind}` : "btn-secondary"}`,
            type: "button",
            disabled: a.disabled || null,
            onclick: () => {
              const keep = a.onClick && a.onClick();
              if (!keep) close();
            },
          }, a.label)))
    : null;
  const modal = PA.h("div", { class: `modal ${wide ? "modal-lg" : ""}`, role: "dialog", "aria-modal": "true" },
    PA.h("div", { class: "modal-header" },
      PA.h("h3", { text: title }),
      PA.h("button", { class: "icon-btn", type: "button", "aria-label": "关闭", onclick: close, html: PA.icon("x") })),
    PA.h("div", { class: "modal-body" }, body),
    footer);
  const backdrop = PA.h("div", { class: "modal-backdrop", onclick: (e) => { if (e.target === backdrop) close(); } }, modal);
  const esc = (e) => { if (e.key === "Escape") { close(); document.removeEventListener("keydown", esc); } };
  document.addEventListener("keydown", esc);
  root.append(backdrop);
  return close;
};

/* ---------- Drawer ---------- */
PA.drawer = ({ title, subtitle, body, actions = [] }) => {
  const root = document.querySelector("#drawer-root");
  const close = () => { wrap.querySelector(".drawer-backdrop").remove(); panel.remove(); };
  const panel = PA.h("aside", { class: "drawer", role: "dialog", "aria-label": title },
    PA.h("div", { class: "drawer-header" },
      PA.h("div", {},
        PA.h("h3", { text: title }),
        subtitle ? PA.h("p", { class: "muted small", text: subtitle }) : null),
      PA.h("button", { class: "icon-btn", type: "button", "aria-label": "关闭", onclick: close, html: PA.icon("x") })),
    PA.h("div", { class: "drawer-body" }, body),
    actions.length
      ? PA.h("div", { class: "drawer-footer" },
          actions.map((a) =>
            PA.h("button", {
              class: `btn ${a.kind ? `btn-${a.kind}` : "btn-secondary"}`,
              type: "button",
              onclick: () => { const keep = a.onClick && a.onClick(); if (!keep) close(); },
            }, a.label)))
      : null);
  const backdrop = PA.h("div", { class: "drawer-backdrop", onclick: close });
  const wrap = PA.h("div", {}, backdrop, panel);
  const esc = (e) => { if (e.key === "Escape") { close(); document.removeEventListener("keydown", esc); } };
  document.addEventListener("keydown", esc);
  root.append(wrap);
  return close;
};

/* ---------- 状态组件 ---------- */
PA.emptyState = ({ icon = "empty", title, text, actionLabel, onAction }) =>
  PA.h("div", { class: "empty-state" },
    PA.h("div", { class: "empty-icon", html: PA.icon(icon) }),
    PA.h("h3", { text: title }),
    PA.h("p", { text: text }),
    actionLabel
      ? PA.h("button", { class: "btn btn-primary", type: "button", onclick: onAction }, actionLabel)
      : null);

PA.errorState = (text, onRetry) =>
  PA.h("div", { class: "error-state", role: "alert" },
    PA.h("span", { html: PA.icon("warning"), style: "flex:none;display:flex" }),
    PA.h("div", { class: "grow" }, PA.h("strong", { text: "加载失败（演示状态）" }), PA.h("div", { text })),
    onRetry ? PA.h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: onRetry }, "重试") : null);

PA.loadingState = (text = "正在加载演示数据…") =>
  PA.h("div", { class: "loading-block" }, PA.h("span", { class: "spinner" }), PA.h("span", { text }));

PA.skeletonBlock = (kind = "card", count = 3) => {
  const box = PA.h("div", { class: kind === "card" ? "stack" : "panel panel-pad" });
  for (let i = 0; i < count; i++)
    box.append(PA.h("div", { class: `skeleton ${kind === "card" ? "skeleton-card" : "skeleton-line"}` }));
  return box;
};

/* 模拟异步加载：先渲染 loading，随后替换为真实内容 */
PA.simulateLoad = (container, renderFn, ms = 450) => {
  PA.clear(container).append(PA.loadingState());
  setTimeout(() => {
    PA.clear(container);
    renderFn(container);
  }, ms);
};

/* ---------- 小部件 ---------- */
PA.statusBadge = (status, label) => {
  const map = {
    verified: ["badge-success", "已验证"],
    pending: ["badge-warning", "待审阅"],
    rejected: ["badge-danger", "已拒绝"],
    active: ["badge-success", "进行中"],
    paused: ["badge-outline", "已暂停"],
    archived: ["badge-outline", "已归档"],
    succeeded: ["badge-success", "成功"],
    failed: ["badge-danger", "失败"],
    running: ["badge-info", "运行中"],
    queued: ["badge-outline", "排队中"],
    demo: ["badge-info", "Demo"],
    planned: ["badge-outline", "Planned"],
    pass: ["badge-success", "PASS"],
    warning: ["badge-warning", "WARNING"],
    fail: ["badge-danger", "FAIL"],
    unknown: ["badge-outline", "UNKNOWN"],
  };
  const [cls, fallback] = map[status] || ["badge-outline", status];
  return PA.h("span", { class: `badge ${cls}` }, PA.h("span", { class: "dot" }), label || fallback);
};

PA.relBadge = (score) => {
  const pct = Math.round(score * 100);
  const cls = score >= 0.85 ? "relevance-high" : score >= 0.7 ? "relevance-mid" : "relevance-low";
  const barCls = score >= 0.85 ? "progress progress-success" : score >= 0.7 ? "progress progress-warning" : "progress";
  return PA.h("span", { class: "score-bar", title: `相关度 ${pct}%` },
    PA.h("span", { class: barCls }, PA.h("div", { style: `width:${pct}%` })),
    PA.h("span", { class: cls, text: `${pct}%` }));
};

PA.meter = (level, max = 5, cls = "") =>
  PA.h("span", { class: `diff-meter ${cls}`, title: `${level}/${max}` },
    Array.from({ length: max }, (_, i) => PA.h("i", { class: i < level ? "on" : "" })));

PA.stars = (n) => PA.h("span", { class: "rec-stars", title: `推荐度 ${n}/5` }, "★".repeat(n) + "☆".repeat(5 - n));

PA.stageBadge = (stageId) => {
  const stage = PA.data.stages.find((s) => s.id === stageId);
  return PA.h("span", { class: "badge badge-primary" }, stage ? stage.label : stageId);
};

/* ---------- 本地 Store（设置 + 交互状态） ---------- */
PA.store = (() => {
  const KEY = "paperagent.workbench.v1";
  const defaults = {
    settings: {
      theme: "light",
      density: "comfortable",
      lang: "zh",
      motion: true,
      demo: true,
      intro: true,
      pageSize: 10,
    },
    currentProject: "crack-3d",
    favorites: {},
    evidenceDecisions: {},
    todosDone: {},
    navCollapsed: false,
  };
  let state;
  try {
    state = { ...defaults, ...(JSON.parse(localStorage.getItem(KEY)) || {}) };
    state.settings = { ...defaults.settings, ...(state.settings || {}) };
  } catch {
    state = { ...defaults };
  }
  const save = () => {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* ignore */ }
  };
  return {
    get: (k) => state[k],
    set: (k, v) => { state[k] = v; save(); },
    settings: () => state.settings,
    setSetting: (k, v) => { state.settings[k] = v; save(); },
    applySettings: () => {
      const s = state.settings;
      document.documentElement.dataset.theme = s.theme;
      document.documentElement.dataset.density = s.density;
      document.documentElement.dataset.motion = s.motion ? "on" : "off";
      const demoBadge = document.querySelector("#demo-badge");
      if (demoBadge) demoBadge.classList.toggle("hidden", !s.demo);
    },
  };
})();

/* 复制文本（带降级） */
PA.copyText = async (text, label = "内容") => {
  try {
    await navigator.clipboard.writeText(text);
    PA.toast(`${label}已复制到剪贴板`, "success");
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.append(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    PA.toast(`${label}已复制到剪贴板`, "success");
  }
};

/* 模拟下载：生成 Blob 触发真实下载（纯前端，无后端） */
PA.mockDownload = (filename, content, mime = "text/plain") => {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 800);
  PA.toast(`已生成演示文件 ${filename}`, "success");
};

PA.views = PA.views || {};
