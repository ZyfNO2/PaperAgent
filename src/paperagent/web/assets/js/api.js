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
        headers: options.body ? { "Content-Type": "application/json" } : undefined,
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
    queryEvidence: (projectId, question, paperIds = [], signal) => request(
      projectPath(projectId, "/evidence/query"),
      { method: "POST", body: { question, paper_ids: paperIds }, signal },
    ),
    resolveLocator: (projectId, locator) => request(projectPath(projectId, "/locator/resolve"), {
      method: "POST", body: { locator },
    }),
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
  };
})();
