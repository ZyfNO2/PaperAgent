"use strict";

const API = "/v1";
const RECENT_KEY = "paperagent.recentTasks.v1";
const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);
const EVENT_TYPES = [
  "task.queued",
  "task.started",
  "task.cancel_requested",
  "task.cancelled",
  "task.succeeded",
  "task.failed",
  "workflow.progress",
];

const state = {
  taskId: null,
  task: null,
  papers: [],
  eventCursor: 0,
  events: new Map(),
  eventSource: null,
  pollTimer: null,
  toastTimer: null,
};

const elements = {
  composerView: document.querySelector("#composer-view"),
  taskView: document.querySelector("#task-view"),
  taskForm: document.querySelector("#task-form"),
  question: document.querySelector("#question"),
  submitButton: document.querySelector("#submit-button"),
  composerError: document.querySelector("#composer-error"),
  newTaskButton: document.querySelector("#new-task-button"),
  recentTaskList: document.querySelector("#recent-task-list"),
  recentEmpty: document.querySelector("#recent-empty"),
  connectionDot: document.querySelector("#connection-dot"),
  connectionText: document.querySelector("#connection-text"),
  taskTitle: document.querySelector("#task-title"),
  taskIdLabel: document.querySelector("#task-id-label"),
  copyLinkButton: document.querySelector("#copy-link-button"),
  cancelButton: document.querySelector("#cancel-button"),
  statusBadge: document.querySelector("#status-badge"),
  statusMessage: document.querySelector("#status-message"),
  progressBar: document.querySelector("#progress-bar"),
  eventList: document.querySelector("#event-list"),
  taskError: document.querySelector("#task-error"),
  evidenceSection: document.querySelector("#evidence-section"),
  paperList: document.querySelector("#paper-list"),
  paperEmpty: document.querySelector("#paper-empty"),
  paperCount: document.querySelector("#paper-count"),
  decisionFilter: document.querySelector("#decision-filter"),
  favoriteFilter: document.querySelector("#favorite-filter"),
  exportSection: document.querySelector("#export-section"),
  exportSelection: document.querySelector("#export-selection"),
  exportButtons: Array.from(document.querySelectorAll(".export-button")),
  toast: document.querySelector("#toast"),
};

function randomKey() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
    return `pwa-${globalThis.crypto.randomUUID()}`;
  }
  return `pwa-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function taskIdFromPath() {
  const match = window.location.pathname.match(/^\/app\/([^/]+)\/?$/);
  return match ? decodeURIComponent(match[1]) : null;
}

function show(element, visible = true) {
  element.classList.toggle("hidden", !visible);
}

function showError(element, message) {
  element.textContent = message;
  show(element, Boolean(message));
}

function toast(message) {
  window.clearTimeout(state.toastTimer);
  elements.toast.textContent = message;
  show(elements.toast, true);
  state.toastTimer = window.setTimeout(() => show(elements.toast, false), 3200);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.headers || {}),
    },
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const detail = payload && payload.detail ? payload.detail : `${response.status} ${response.statusText}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

function readRecentTasks() {
  try {
    const value = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
    return Array.isArray(value) ? value.filter((item) => item && item.taskId).slice(0, 8) : [];
  } catch {
    return [];
  }
}

function saveRecentTask(taskId, title) {
  const existing = readRecentTasks().filter((item) => item.taskId !== taskId);
  existing.unshift({ taskId, title: title.slice(0, 100), savedAt: new Date().toISOString() });
  localStorage.setItem(RECENT_KEY, JSON.stringify(existing.slice(0, 8)));
  renderRecentTasks();
}

function renderRecentTasks() {
  const tasks = readRecentTasks();
  elements.recentTaskList.replaceChildren();
  show(elements.recentEmpty, tasks.length === 0);
  for (const task of tasks) {
    const item = document.createElement("li");
    item.className = "recent-item";
    const link = document.createElement("a");
    link.href = `/app/${encodeURIComponent(task.taskId)}`;
    if (task.taskId === state.taskId) {
      link.setAttribute("aria-current", "page");
    }
    const title = document.createElement("strong");
    title.textContent = task.title || "Research task";
    const id = document.createElement("small");
    id.textContent = task.taskId;
    link.append(title, id);
    item.append(link);
    elements.recentTaskList.append(item);
  }
}

function setConnection(online, label = null) {
  elements.connectionDot.classList.toggle("online", online);
  elements.connectionDot.classList.toggle("offline", !online);
  elements.connectionText.textContent = label || (online ? "在线" : "离线");
}

function resetRuntime() {
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
  if (state.pollTimer) {
    window.clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }
  state.task = null;
  state.papers = [];
  state.eventCursor = 0;
  state.events.clear();
}

function openComposer({ replace = false } = {}) {
  resetRuntime();
  state.taskId = null;
  show(elements.composerView, true);
  show(elements.taskView, false);
  showError(elements.composerError, "");
  if (replace) {
    window.history.pushState({}, "", "/app");
  }
  renderRecentTasks();
  elements.question.focus();
}

function progressForStatus(status) {
  return {
    queued: 7,
    running: 45,
    cancel_requested: 70,
    cancelled: 100,
    succeeded: 100,
    failed: 100,
  }[status] || 4;
}

function statusMessage(task) {
  const messages = {
    queued: "任务已进入队列，等待单进程 Runner 执行。",
    running: "工作流正在执行。页面会通过轮询读取持久状态，并尝试使用 SSE 接收增量事件。",
    cancel_requested: "已请求取消；当前边界完成后将停止后续工作。",
    cancelled: "任务已取消。",
    succeeded: "任务已完成。可以审阅论文卡片并导出结果。",
    failed: "任务失败。错误合同不会暴露原始异常或凭证。",
  };
  return messages[task.status] || `当前状态：${task.status}`;
}

function renderTask() {
  const task = state.task;
  if (!task) return;
  const title = task.request && task.request.question ? task.request.question : "Research task";
  elements.taskTitle.textContent = title;
  elements.taskIdLabel.textContent = task.task_id;
  elements.statusBadge.textContent = task.status;
  elements.statusBadge.className = `status-badge ${task.status}`;
  elements.statusMessage.textContent = statusMessage(task);
  elements.progressBar.style.width = `${progressForStatus(task.status)}%`;
  show(
    elements.cancelButton,
    ["queued", "running", "cancel_requested"].includes(task.status),
  );
  const errorMessage = task.error ? `${task.error.code}: ${task.error.message}` : "";
  showError(elements.taskError, errorMessage);
  show(elements.evidenceSection, task.status === "succeeded");
  show(elements.exportSection, task.status === "succeeded");
  saveRecentTask(task.task_id, title);
}

function eventLabel(event) {
  const labels = {
    "task.queued": "任务进入队列",
    "task.started": "Runner 开始执行",
    "task.cancel_requested": "收到取消请求",
    "task.cancelled": "任务已取消",
    "task.succeeded": "任务完成",
    "task.failed": "任务失败",
    "workflow.progress": "工作流进度更新",
  };
  return labels[event.event_type] || event.event_type;
}

function mergeEvent(event) {
  if (!event || typeof event.sequence !== "number" || state.events.has(event.sequence)) return;
  state.events.set(event.sequence, event);
  state.eventCursor = Math.max(state.eventCursor, event.sequence);
  renderEvents();
}

function renderEvents() {
  const events = Array.from(state.events.values()).sort((a, b) => a.sequence - b.sequence);
  elements.eventList.replaceChildren();
  for (const event of events.slice(-30)) {
    const item = document.createElement("li");
    const time = document.createElement("time");
    time.dateTime = event.created_at;
    time.textContent = new Date(event.created_at).toLocaleTimeString();
    const text = document.createElement("span");
    text.textContent = `${event.sequence}. ${eventLabel(event)}`;
    item.append(time, text);
    elements.eventList.append(item);
  }
}

async function loadEvents() {
  if (!state.taskId) return;
  const page = await requestJson(
    `${API}/tasks/${encodeURIComponent(state.taskId)}/events?after=${state.eventCursor}&limit=100`,
  );
  for (const event of page.events || []) mergeEvent(event);
}

function connectSse() {
  if (!state.taskId || !globalThis.EventSource || state.eventSource) return;
  const url = `${API}/tasks/${encodeURIComponent(state.taskId)}/events/stream?after=${state.eventCursor}`;
  const source = new EventSource(url);
  state.eventSource = source;
  source.onopen = () => setConnection(true, "SSE 已连接");
  source.onerror = () => {
    if (state.task && TERMINAL.has(state.task.status)) {
      source.close();
      state.eventSource = null;
      setConnection(true, "任务已完成");
    } else {
      setConnection(navigator.onLine, "SSE 重连中，轮询仍在运行");
    }
  };
  for (const type of EVENT_TYPES) {
    source.addEventListener(type, (message) => {
      try {
        mergeEvent(JSON.parse(message.data));
      } catch {
        // Polling remains the source of recovery for malformed/disconnected SSE frames.
      }
    });
  }
}

async function loadPapers() {
  if (!state.taskId) return;
  const params = new URLSearchParams({ limit: "100" });
  if (elements.decisionFilter.value) params.set("decision", elements.decisionFilter.value);
  if (elements.favoriteFilter.checked) params.set("favorite", "true");
  const page = await requestJson(
    `${API}/tasks/${encodeURIComponent(state.taskId)}/papers?${params.toString()}`,
  );
  state.papers = page.items || [];
  renderPapers();
}

function locatorHref(locator) {
  if (locator.startsWith("doi:")) return `https://doi.org/${locator.slice(4)}`;
  if (/^https?:\/\//.test(locator)) return locator;
  return null;
}

function makeTag(text, extraClass = "") {
  const tag = document.createElement("span");
  tag.className = `tag ${extraClass}`.trim();
  tag.textContent = text;
  return tag;
}

function reviewButton(label, decision, card) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `review-button ${card.decision === decision ? "active" : ""}`.trim();
  button.textContent = label;
  button.addEventListener("click", () => updateReview(card, { decision }));
  if (
    decision === "accepted" &&
    ["rejected", "failed_verification"].includes(card.verification_status)
  ) {
    button.disabled = true;
    button.title = "验证失败的证据不能在 MVP 中强制接受";
  }
  return button;
}

function renderPapers() {
  elements.paperList.replaceChildren();
  elements.paperCount.textContent = `${state.papers.length} 篇论文卡片`;
  show(elements.paperEmpty, state.papers.length === 0);
  for (const card of state.papers) {
    const article = document.createElement("article");
    article.className = "paper-card";
    article.dataset.paperId = card.paper_id;

    const header = document.createElement("div");
    header.className = "paper-card-header";
    const titleBox = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = card.title;
    const href = locatorHref(card.locator);
    const locator = document.createElement(href ? "a" : "span");
    locator.className = "paper-locator";
    locator.textContent = card.locator;
    if (href) {
      locator.href = href;
      locator.target = "_blank";
      locator.rel = "noopener noreferrer";
    }
    titleBox.append(title, locator);
    const verificationClass = ["rejected", "failed_verification"].includes(
      card.verification_status,
    )
      ? "failed"
      : "";
    header.append(titleBox, makeTag(card.verification_status, verificationClass));

    const summary = document.createElement("p");
    summary.className = "paper-summary";
    summary.textContent = card.summary || "暂无摘要。";

    const tags = document.createElement("div");
    tags.className = "tag-list";
    for (const gap of card.gap_ids || []) tags.append(makeTag(gap));
    tags.append(makeTag(`review: ${card.decision}`));
    if (card.favorite) tags.append(makeTag("favorite"));

    const actions = document.createElement("div");
    actions.className = "review-actions";
    actions.append(
      reviewButton("待审阅", "pending", card),
      reviewButton("接受", "accepted", card),
      reviewButton("拒绝", "rejected", card),
    );
    const favorite = document.createElement("button");
    favorite.type = "button";
    favorite.className = `review-button favorite-button ${card.favorite ? "active" : ""}`.trim();
    favorite.textContent = card.favorite ? "★ 已收藏" : "☆ 收藏";
    favorite.addEventListener("click", () => updateReview(card, { favorite: !card.favorite }));
    actions.append(favorite);

    article.append(header, summary, tags, actions);
    elements.paperList.append(article);
  }
}

async function updateReview(card, patch) {
  if (!state.taskId) return;
  const decision = patch.decision || card.decision;
  const favorite = patch.favorite === undefined ? card.favorite : patch.favorite;
  try {
    await requestJson(
      `${API}/tasks/${encodeURIComponent(state.taskId)}/papers/${encodeURIComponent(card.paper_id)}/review`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          favorite,
          expected_version: card.review_version,
        }),
      },
    );
    await loadPapers();
    toast("审阅状态已保存");
  } catch (error) {
    toast(`保存失败：${error.message}`);
    await loadPapers().catch(() => undefined);
  }
}

async function pollTask() {
  if (!state.taskId) return;
  try {
    state.task = await requestJson(`${API}/tasks/${encodeURIComponent(state.taskId)}`);
    setConnection(true, state.eventSource ? "SSE + 轮询" : "轮询已连接");
    renderTask();
    await loadEvents();
    if (state.task.status === "succeeded") await loadPapers();
    if (TERMINAL.has(state.task.status)) {
      if (state.eventSource) state.eventSource.close();
      state.eventSource = null;
      return;
    }
    connectSse();
  } catch (error) {
    setConnection(false, navigator.onLine ? "服务暂不可用" : "设备离线");
    showError(elements.taskError, `读取任务失败：${error.message}`);
  }
  state.pollTimer = window.setTimeout(pollTask, 1500);
}

async function openTask(taskId, { navigate = true } = {}) {
  resetRuntime();
  state.taskId = taskId;
  show(elements.composerView, false);
  show(elements.taskView, true);
  show(elements.evidenceSection, false);
  show(elements.exportSection, false);
  showError(elements.taskError, "");
  elements.taskTitle.textContent = "正在读取任务";
  elements.taskIdLabel.textContent = taskId;
  if (navigate) window.history.pushState({}, "", `/app/${encodeURIComponent(taskId)}`);
  renderRecentTasks();
  await pollTask();
}

async function submitTask(event) {
  event.preventDefault();
  const question = elements.question.value.trim();
  if (question.length < 3) return;
  showError(elements.composerError, "");
  elements.submitButton.disabled = true;
  elements.submitButton.textContent = "正在创建…";
  try {
    const accepted = await requestJson(`${API}/tasks`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": randomKey(),
      },
      body: JSON.stringify({
        request: { question },
        metadata: { client: "paperagent-pwa-v0.5" },
      }),
    });
    saveRecentTask(accepted.task_id, question);
    await openTask(accepted.task_id);
  } catch (error) {
    showError(elements.composerError, `创建任务失败：${error.message}`);
  } finally {
    elements.submitButton.disabled = false;
    elements.submitButton.textContent = "创建研究任务";
  }
}

async function cancelTask() {
  if (!state.taskId) return;
  elements.cancelButton.disabled = true;
  try {
    const result = await requestJson(
      `${API}/tasks/${encodeURIComponent(state.taskId)}/cancel`,
      { method: "POST" },
    );
    toast(result.accepted ? "取消请求已提交" : "任务已经是终态");
    await pollTask();
  } catch (error) {
    toast(`取消失败：${error.message}`);
  } finally {
    elements.cancelButton.disabled = false;
  }
}

async function copyTaskLink() {
  try {
    await navigator.clipboard.writeText(window.location.href);
    toast("任务链接已复制");
  } catch {
    toast("浏览器未允许自动复制，请手动复制地址栏链接");
  }
}

async function downloadExport(format) {
  if (!state.taskId) return;
  const selection = elements.exportSelection.value;
  const url = `${API}/tasks/${encodeURIComponent(state.taskId)}/exports/${format}?selection=${selection}`;
  try {
    const response = await fetch(url, { headers: { Accept: "*/*" } });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : `paperagent-export.${format}`;
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
    const checksum = response.headers.get("x-paperagent-sha256");
    toast(checksum ? `导出完成 · SHA-256 ${checksum.slice(0, 12)}…` : "导出完成");
  } catch (error) {
    toast(`导出失败：${error.message}`);
  }
}

function wireEvents() {
  elements.taskForm.addEventListener("submit", submitTask);
  elements.newTaskButton.addEventListener("click", () => openComposer({ replace: true }));
  elements.cancelButton.addEventListener("click", cancelTask);
  elements.copyLinkButton.addEventListener("click", copyTaskLink);
  elements.decisionFilter.addEventListener("change", () => loadPapers().catch(console.error));
  elements.favoriteFilter.addEventListener("change", () => loadPapers().catch(console.error));
  for (const button of elements.exportButtons) {
    button.addEventListener("click", () => downloadExport(button.dataset.format));
  }
  window.addEventListener("online", () => setConnection(true));
  window.addEventListener("offline", () => setConnection(false));
  window.addEventListener("popstate", () => {
    const taskId = taskIdFromPath();
    if (taskId) openTask(taskId, { navigate: false });
    else openComposer();
  });
}

async function boot() {
  renderRecentTasks();
  wireEvents();
  setConnection(navigator.onLine);
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/app/service-worker.js", { scope: "/app" }).catch(() => undefined);
  }
  const taskId = taskIdFromPath();
  if (taskId) await openTask(taskId, { navigate: false });
  else openComposer();
}

boot().catch((error) => {
  setConnection(false, "初始化失败");
  showError(elements.composerError, `初始化失败：${error.message}`);
});
