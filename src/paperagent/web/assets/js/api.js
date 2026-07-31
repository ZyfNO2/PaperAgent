"use strict";

window.PA = window.PA || {};

PA.api = (() => {
  const EXPECTED_SCHEMA = "academic.v1";
  const TIMEOUT_MS = 15000;

  class APIError extends Error {
    constructor(code, message, status = 0, retryable = false) {
      super(message);
      this.name = "APIError";
      this.code = code;
      this.status = status;
      this.retryable = retryable;
    }
  }

  async function request(path, options = {}) {
    const controller = new AbortController();
    const external = options.signal;
    const abort = () => controller.abort(external && external.reason);
    if (external) {
      if (external.aborted) abort();
      else external.addEventListener("abort", abort, { once: true });
    }
    const timer = setTimeout(() => controller.abort("timeout"), options.timeoutMs || TIMEOUT_MS);
    try {
      const response = await fetch(path, {
        method: options.method || "GET",
        headers: {
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...(options.headers || {}),
        },
        body: options.body ? JSON.stringify(options.body) : undefined,
        signal: controller.signal,
        credentials: "same-origin",
      });
      let payload;
      try {
        payload = await response.json();
      } catch (_) {
        throw new APIError("malformed_response", "API 返回了非 JSON 数据。", response.status);
      }
      if (!response.ok) {
        const detail = payload && payload.detail && typeof payload.detail === "object"
          ? payload.detail : {};
        throw new APIError(
          detail.code || "request_failed",
          detail.message || `请求失败（HTTP ${response.status}）`,
          response.status,
          Boolean(detail.retryable),
        );
      }
      return payload;
    } catch (error) {
      if (error instanceof APIError) throw error;
      if (controller.signal.aborted) {
        throw new APIError("request_cancelled", "请求已取消或超时。", 0, true);
      }
      throw new APIError("network_failure", "无法连接 PaperAgent API。", 0, true);
    } finally {
      clearTimeout(timer);
      if (external) external.removeEventListener("abort", abort);
    }
  }

  async function requestBlob(path, body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort("timeout"), TIMEOUT_MS);
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
        credentials: "same-origin",
      });
      if (!response.ok) {
        let detail = {};
        try { detail = (await response.json()).detail || {}; } catch (_) { /* bounded below */ }
        throw new APIError(
          detail.code || "asset_request_failed",
          detail.message || `Asset request failed (HTTP ${response.status})`,
          response.status,
          Boolean(detail.retryable),
        );
      }
      return response.blob();
    } catch (error) {
      if (error instanceof APIError) throw error;
      if (controller.signal.aborted) {
        throw new APIError("request_cancelled", "Asset request timed out.", 0, true);
      }
      throw new APIError("network_failure", "Unable to read the PaperClaw asset.", 0, true);
    } finally {
      clearTimeout(timer);
    }
  }

  const projectPath = (projectId, suffix = "") =>
    `/v1/academic/projects/${encodeURIComponent(projectId)}${suffix}`;

  async function loadProjectData(projectId) {
    const [papers, artifacts] = await Promise.all([
      request(projectPath(projectId, "/papers")),
      request(projectPath(projectId, "/artifacts")),
    ]);
    return { papers: papers.papers || [], artifacts: artifacts.artifacts || [] };
  }

  return {
    APIError,
    request,
    loadProjectData,
    async bootstrap() {
      const params = new URLSearchParams(location.search);
      if (params.get("demo") === "1") {
        return { mode: "demo", model: PA.demoData };
      }
      const capabilities = await request("/v1/academic/capabilities");
      if (capabilities.schema_version !== EXPECTED_SCHEMA) {
        throw new APIError("schema_incompatible", "Academic API schema 不兼容。", 409);
      }
      if (!capabilities.paperclaw_configured) {
        throw new APIError("paperclaw_not_configured", "PaperClaw Academic API 尚未配置。", 503);
      }
      const result = await request("/v1/academic/projects");
      const projects = (result.projects || []).map((item) => ({
        id: item.project_id,
        name: item.name,
        status: "active",
        stage: "evidence",
        paperCount: 0,
        evidenceCount: 0,
        gateStatus: "REVISE",
      }));
      const selected = localStorage.getItem("paperagent.currentProject");
      const current = projects.find((item) => item.id === selected) || projects[0] || null;
      const detail = current ? await loadProjectData(current.id) : { papers: [], artifacts: [] };
      if (current) current.paperCount = detail.papers.length;
      return {
        mode: "production",
        model: {
          projects,
          papers: detail.papers,
          evidence: [],
          artifacts: detail.artifacts,
          runs: [],
        },
      };
    },
    createProject: (name) => request("/v1/academic/projects", { method: "POST", body: { name } }),
    importPaper: (projectId, sourcePath) => request(projectPath(projectId, "/papers/import"), {
      method: "POST", body: { source_path: sourcePath },
    }),
    parsePaper: (projectId, paperId) => request(
      projectPath(projectId, `/papers/${encodeURIComponent(paperId)}/parse`), { method: "POST" },
    ),
    buildIndex: (projectId) => request(projectPath(projectId, "/index"), { method: "POST" }),
    queryEvidence: (projectId, question, paperIds = [], signal) => request(
      projectPath(projectId, "/evidence/query"),
      { method: "POST", body: { question, paper_ids: paperIds }, signal },
    ),
    resolveLocator: (projectId, locator) => request(projectPath(projectId, "/locator/resolve"), {
      method: "POST", body: { locator },
    }),
    readAsset: (projectId, locator, assetHash) => requestBlob(
      projectPath(projectId, "/locator/asset"),
      { locator, asset_hash: assetHash },
    ),
    getArtifact: (projectId, artifactId) => request(
      projectPath(projectId, `/artifacts/${encodeURIComponent(artifactId)}`),
    ),
    reviewArtifact: (projectId, artifactId, decision, note) => request(
      projectPath(projectId, `/artifacts/${encodeURIComponent(artifactId)}/review`),
      {
        method: "POST",
        body: {
          decision,
          note,
          idempotency_key: `web-${artifactId}-${decision}-${Date.now()}`,
        },
      },
    ),
    generateArtifacts: (projectId, hypothesis, baselinePaperId, modulePaperIds) => request(
      projectPath(projectId, "/artifacts/generate"),
      {
        method: "POST",
        body: {
          hypothesis,
          baseline_paper_id: baselinePaperId,
          module_paper_ids: modulePaperIds,
        },
      },
    ),
    listArtifacts: (projectId) => request(projectPath(projectId, "/artifacts")),
    createTask: (payload, idempotencyKey) => request("/v1/tasks", {
      method: "POST",
      body: payload,
      headers: { "Idempotency-Key": idempotencyKey },
    }),
    getTask: (taskId) => request(`/v1/tasks/${encodeURIComponent(taskId)}`),
    cancelTask: (taskId) => request(`/v1/tasks/${encodeURIComponent(taskId)}/cancel`, {
      method: "POST",
    }),
    async pollTask(taskId, { signal, intervalMs = 500, maxPolls = 120 } = {}) {
      for (let poll = 0; poll < maxPolls; poll += 1) {
        const task = await request(`/v1/tasks/${encodeURIComponent(taskId)}`, { signal });
        if (["succeeded", "failed", "cancelled"].includes(task.status)) return task;
        await new Promise((resolve, reject) => {
          const timer = setTimeout(resolve, intervalMs);
          if (signal) signal.addEventListener("abort", () => {
            clearTimeout(timer);
            reject(new APIError("request_cancelled", "任务轮询已取消。", 0, true));
          }, { once: true });
        });
      }
      throw new APIError("task_poll_exhausted", "任务在轮询预算内未结束。", 408, true);
    },
  };
})();
