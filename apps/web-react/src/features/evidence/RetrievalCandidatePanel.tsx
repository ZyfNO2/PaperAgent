// Session 61: RetrievalCandidatePanel — 用户侧多源检索候选面板.
// Session 64 T6: 按角色分组展示 (baseline / parallel / modules / datasets / dev)
// ponytail:
// - 不引 store / context, useState 局部足够
// - 不调 LLM; 不复用 RAG Eval 的 metric 表格
// - "加入证据" 复用现有 retrieval/import (M7 candidate_actions 暂未上线为路由)
// - "加入文献库" 复用现有 paper-library/manual
// - "标记不相关" 仅 UI 灰化, 不发请求 (M7 标 irrelevant 后端尚未挂路由)
// - 角色分组复用后端 literature_roles (S64 T3); 模块矩阵复用 module_matrix (S64 T4)
// - 开发者模式: 展示 clean_summary 计数 + 原始 score + source 轨迹; 不再发请求

import { useEffect, useMemo, useState } from "react";
import { ApiError, apiClient } from "../../app/apiClient";
import { Badge } from "../../components/ui/Badge";
import { Tabs } from "../../components/ui/Tabs";

const DEFAULT_PROJECT = "demo-local-rag";
const API_PREFIX = "/api/v1";

// ------- 与后端 schemas_retrieval.py 对齐的窄类型 ------- //

type CandidateType = "paper" | "dataset" | "repo" | "project_page" | "note";
type Source =
  | "openalex"
  | "semantic_scholar"
  | "arxiv"
  | "github"
  | "huggingface"
  | "kaggle"
  | "manual_fallback";
type RetrievalStatus = "running" | "completed" | "partial" | "failed";
type LiteratureRole =
  | "baseline_framework"
  | "baseline_method"
  | "parallel_application_paper"
  | "module_improvement_paper"
  | "dataset_paper"
  | "survey"
  | "irrelevant";

interface RoleAssignment {
  candidate_id: string;
  role: LiteratureRole;
  base_framework?: string | null;
  modules_added?: string[];
  datasets?: string[];
  metrics?: string[];
  code_url?: string | null;
  reproducibility?: string | null;
  borrowable_ideas?: string[];
  risk_notes?: string[];
  reason?: string;
}

interface ModuleEntry {
  base?: string;
  module_a?: string;
  module_b?: string | null;
  dataset?: string;
  metrics?: string[];
  paper_title?: string;
  paper_url?: string | null;
  improvement_description?: string;
  risk_notes?: string;
}

interface ModuleMatrix {
  topic?: string;
  domain?: string;
  entries?: ModuleEntry[];
  missing_module_types?: string[];
  baseline_options?: Array<Record<string, unknown>>;
  recommended_combinations?: Array<Record<string, unknown>>;
}

interface RetrievalCandidate {
  candidate_id: string;
  project_id: string;
  candidate_type: CandidateType;
  source: Source;
  title: string;
  url: string | null;
  year: number | null;
  authors: string[];
  abstract: string | null;
  doi: string | null;
  arxiv_id: string | null;
  repo_full_name: string | null;
  dataset_slug: string | null;
  stars: number | null;
  citation_count: number | null;
  matched_keywords: string[];
  retrieval_score: number;
  is_duplicate: boolean;
  already_in_ledger: boolean;
  raw: Record<string, unknown>;
}

interface QueryPlan {
  project_id: string;
  raw_topic: string;
  paper_queries: { layer: string; queries: string[] }[];
  dataset_queries: { layer: string; queries: string[] }[];
  repo_queries: { layer: string; queries: string[] }[];
}

interface SourceResult {
  source: Source;
  status: RetrievalStatus;
  candidate_count: number;
  error: string | null;
  duration_ms: number;
}

interface GapItem {
  topic?: string;
  reason?: string;
  next_step_queries?: string[];
}

interface RetrievalRun {
  run_id: string;
  project_id: string;
  query_plan: QueryPlan;
  sources: Source[];
  source_results: SourceResult[];
  started_at: string;
  finished_at: string | null;
  status: RetrievalStatus;
  total_candidates: number;
  imported_count: number;
  errors: string[];
  candidates: RetrievalCandidate[];
  gap_report: { gaps?: GapItem[] } | null;
  retry_round: number;
  // S64: 后端 orchestrator 已挂上, 旧 schema 默认值保证向后兼容
  clean_summary?: Record<string, number> | null;
  web_datasets?: Array<Record<string, unknown>>;
  literature_roles?: RoleAssignment[];
  module_matrix?: ModuleMatrix | null;
}

interface RetrievalImportResponse {
  run_id: string;
  imported: number;
  skipped_duplicates: number;
  skipped_rejected: number;
  evidence_ids: string[];
  skipped_evidence_ids: string[];
  message: string;
}

interface PaperManualCreateResponse {
  paper_id: string;
  status?: string;
  parse_status?: string;
  chunk_count?: number;
  is_duplicate?: boolean;
  message?: string;
}

interface Flash {
  kind: "ok" | "warn" | "err";
  text: string;
}

export interface RetrievalCandidatePanelProps {
  testId?: string;
  projectId?: string;
  topic?: string;
  apiPrefix?: string;
}

function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.body === "string") return error.body;
    if (error.body && typeof error.body === "object" && "detail" in (error.body as Record<string, unknown>)) {
      const detail = (error.body as { detail?: unknown }).detail;
      if (typeof detail === "string") return detail;
      return JSON.stringify(error.body, null, 2);
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "未知错误";
}

function statusTone(status: RetrievalStatus): "ok" | "warn" | "err" | "info" {
  if (status === "completed") return "ok";
  if (status === "partial") return "warn";
  if (status === "failed") return "err";
  return "info";
}

function splitKeywords(text: string): string[] {
  const parts = text
    .split(/[\s,;。、，；]+/g)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);
  return parts.length > 0 ? parts : [text.trim()].filter(Boolean);
}

const ROLE_LABELS: Record<LiteratureRole, string> = {
  baseline_framework: "Baseline 框架",
  baseline_method: "Baseline 方法",
  parallel_application_paper: "平行应用论文",
  module_improvement_paper: "模块改进论文",
  dataset_paper: "数据集论文",
  survey: "综述 (Survey)",
  irrelevant: "不相关 (已过滤)",
};

export function RetrievalCandidatePanel({
  testId,
  projectId = DEFAULT_PROJECT,
  topic,
  apiPrefix = API_PREFIX,
}: RetrievalCandidatePanelProps) {
  const [topicDraft, setTopicDraft] = useState<string>(topic ?? "");
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<Flash | null>(null);
  const [run, setRun] = useState<RetrievalRun | null>(null);
  const [dimmed, setDimmed] = useState<Set<string>>(new Set());
  const [importedEid, setImportedEid] = useState<Map<string, string>>(new Map());
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [devMode, setDevMode] = useState<boolean>(false);

  useEffect(() => {
    if (topic && topic.length > 0 && topicDraft.length === 0) {
      setTopicDraft(topic);
    }
  }, [topic, topicDraft.length]);

  async function runSearch() {
    const next = topicDraft.trim();
    if (!next || busy) return;
    setBusy(true);
    setError(null);
    setFlash(null);
    setDimmed(new Set());
    setImportedEid(new Map());
    try {
      const body = {
        scope: ["paper", "dataset", "repo"] as CandidateType[],
        sources: ["openalex", "arxiv", "github", "huggingface"] as Source[],
        top_k_per_source: 8,
        extra_keywords: splitKeywords(next),
      };
      const data = await apiClient.post<RetrievalRun>(
        `${apiPrefix}/one-topic/${projectId}/retrieval/search`,
        body,
      );
      setRun(data);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setBusy(false);
    }
  }

  async function addToEvidence(candidate: RetrievalCandidate) {
    if (!run) return;
    setActionBusy(`evidence-${candidate.candidate_id}`);
    setFlash(null);
    try {
      const resp = await apiClient.post<RetrievalImportResponse>(
        `${apiPrefix}/one-topic/${projectId}/retrieval/import`,
        {
          run_id: run.run_id,
          candidate_ids: [candidate.candidate_id],
          workspace_lane: "user_preferred",
          auto_verify: false,
        },
      );
      const eid = resp.evidence_ids[0];
      if (eid) {
        setImportedEid((prev) => {
          const next = new Map(prev);
          next.set(candidate.candidate_id, eid);
          return next;
        });
      }
      setFlash({
        kind: resp.imported > 0 ? "ok" : "warn",
        text:
          resp.imported > 0
            ? `已加入证据: ${eid ?? resp.message ?? "ok"}`
            : `未导入: ${resp.message || "重复或被拒"}`,
      });
    } catch (e) {
      setFlash({ kind: "err", text: `加入证据失败: ${formatError(e)}` });
    } finally {
      setActionBusy(null);
    }
  }

  async function addToLibrary(candidate: RetrievalCandidate) {
    setActionBusy(`library-${candidate.candidate_id}`);
    setFlash(null);
    try {
      const resp = await apiClient.post<PaperManualCreateResponse>(
        `${apiPrefix}/projects/${projectId}/paper-library/manual`,
        {
          title: candidate.title,
          text: candidate.abstract || candidate.title,
          url: candidate.url,
          tags: [candidate.source, candidate.candidate_type],
        },
      );
      setFlash({
        kind: resp.status === "duplicate" ? "warn" : "ok",
        text: resp.status === "duplicate"
          ? `文献已存在: ${resp.paper_id}`
          : `已加入文献库: ${resp.paper_id}`,
      });
    } catch (e) {
      setFlash({ kind: "err", text: `加入文献库失败: ${formatError(e)}` });
    } finally {
      setActionBusy(null);
    }
  }

  function markIrrelevant(candidate: RetrievalCandidate) {
    setDimmed((prev) => {
      const next = new Set(prev);
      next.add(candidate.candidate_id);
      return next;
    });
    setFlash({ kind: "warn", text: `已标记不相关: ${candidate.title}` });
  }

  function retrySimilar(candidate: RetrievalCandidate) {
    const queries = [
      `${candidate.title} implementation`,
      `${candidate.title} survey`,
      `${candidate.title} benchmark`,
    ];
    const merged = [...new Set([...splitKeywords(topicDraft), ...queries])];
    setTopicDraft(merged.join(" "));
    setFlash({ kind: "warn", text: `已补搜关键词, 点击"开始检索"重跑` });
  }

  // ---- 角色分组: candidate_id -> RoleAssignment ---- //
  const roleById = useMemo(() => {
    const map = new Map<string, RoleAssignment>();
    (run?.literature_roles ?? []).forEach((r) => map.set(r.candidate_id, r));
    return map;
  }, [run?.literature_roles]);

  const roleOf = (c: RetrievalCandidate): LiteratureRole | null =>
    roleById.get(c.candidate_id)?.role ?? null;

  const papers = (run?.candidates ?? []).filter((c) => c.candidate_type === "paper");
  const datasets = (run?.candidates ?? []).filter((c) => c.candidate_type === "dataset");
  const repos = (run?.candidates ?? []).filter((c) => c.candidate_type === "repo");

  // 论文按角色分桶 (survey 仅背景, irrelevant 不入主视图)
  const papersByRole = useMemo(() => {
    const buckets: Record<LiteratureRole, RetrievalCandidate[]> = {
      baseline_framework: [],
      baseline_method: [],
      parallel_application_paper: [],
      module_improvement_paper: [],
      dataset_paper: [],
      survey: [],
      irrelevant: [],
    };
    papers.forEach((p) => {
      const r = roleOf(p);
      if (r) buckets[r].push(p);
      else buckets.parallel_application_paper.push(p); // 没角色的论文默认归"平行"
    });
    return buckets;
  }, [papers, roleById]);

  const surveyPapers = papersByRole.survey;
  const irrelevantPapers = papersByRole.irrelevant;

  // 主视图: baseline + parallel + module (保持 keep, 不含 survey / irrelevant)
  const baselinePapers = [
    ...papersByRole.baseline_framework,
    ...papersByRole.baseline_method,
  ];
  const parallelPapers = papersByRole.parallel_application_paper;
  const modulePapers = papersByRole.module_improvement_paper;

  const cleanSummary = run?.clean_summary ?? null;
  const moduleMatrix = run?.module_matrix ?? null;

  return (
    <section className="pa-uw-zone" data-testid={testId ?? "retrieval-panel"}>
      <header className="pa-uw-zone__head">
        <span className="pa-uw-zone__cap">E</span>
        <h2 className="pa-uw-zone__title">多源检索候选</h2>
        <div className="pa-uw-zone__meta">
          openalex / arxiv / github / huggingface, 候选可入证据 / 入文献库
        </div>
      </header>
      <div className="pa-uw-zone__body">
        <div className="pa-uw-form">
          <label className="pa-uw-form__row">
            <span className="pa-uw-form__label">检索关键词</span>
            <input
              className="pa-uw-form__input"
              type="text"
              value={topicDraft}
              onChange={(e) => setTopicDraft(e.target.value)}
              placeholder="例: steel defect detection YOLO"
              data-testid="retrieval-topic-input"
            />
          </label>
          <div className="pa-uw-form__actions">
            <button
              type="button"
              className="pa-btn pa-btn--primary pa-btn--md"
              onClick={runSearch}
              disabled={busy || topicDraft.trim().length === 0}
              data-testid="retrieval-search-btn"
            >
              {busy ? "检索中..." : "开始检索"}
            </button>
            {run ? (
              <span className="pa-small pa-muted" data-testid="retrieval-run-id">
                run_id: {run.run_id}
              </span>
            ) : null}
            <button
              type="button"
              className={
                "pa-btn pa-btn--ghost pa-btn--md" + (devMode ? " pa-btn--active" : "")
              }
              onClick={() => setDevMode((v) => !v)}
              data-testid="retrieval-dev-toggle"
              title="开发者模式: 显示已过滤候选 / clean 原因 / source 轨迹 / 原始分数"
            >
              {devMode ? "开发者模式 ON" : "开发者模式"}
            </button>
          </div>
        </div>

        {busy ? (
          <div className="pa-faint" data-testid="retrieval-loading">
            正在调用多源检索, 请稍等...
          </div>
        ) : null}

        {error ? (
          <div className="pa-uw-form__error" data-testid="retrieval-error">
            {error}
          </div>
        ) : null}

        {flash ? (
          <div className="pa-small pa-muted" data-testid="retrieval-flash">
            {flash.text}
          </div>
        ) : null}

        {run && run.retry_round >= 1 ? (
          <div className="pa-uw-zone__meta" data-testid="retrieval-retry-banner">
            retry_round: {run.retry_round}; 已基于补搜结果再次跑过
          </div>
        ) : null}

        {run ? (
          <div className="pa-uw-result-group" data-testid="retrieval-sources">
            <div className="pa-uw-result-group__title">来源执行状态</div>
            {run.source_results.length === 0 ? (
              <div className="pa-faint">暂无来源结果</div>
            ) : (
              <ul className="pa-uw-result-list">
                {run.source_results.map((sr) => (
                  <li
                    key={sr.source}
                    className="pa-uw-result-item"
                    data-testid={`retrieval-source-${sr.source}`}
                  >
                    <div className="pa-uw-result-item__head">
                      <strong>{sr.source}</strong>
                      <Badge tone={statusTone(sr.status)} testId={`retrieval-source-tone-${sr.source}`}>
                        {sr.status}
                      </Badge>
                    </div>
                    <div className="pa-uw-result-item__meta">
                      {sr.candidate_count} candidates · {sr.duration_ms}ms
                    </div>
                    {sr.error ? (
                      <div className="pa-uw-result-item__summary pa-uw-result-item__summary--err">
                        {sr.error}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}

        {run ? (
          <div className="pa-uw-analysis-grid pa-uw-analysis-grid--triple">
            <CandidateList
              testId="retrieval-papers"
              title={`论文 (${papers.length})`}
              candidates={papers}
              roleById={roleById}
              dimmed={dimmed}
              importedEid={importedEid}
              actionBusy={actionBusy}
              devMode={devMode}
              onAddEvidence={addToEvidence}
              onAddLibrary={addToLibrary}
              onReject={markIrrelevant}
              onRetry={retrySimilar}
            />
            <CandidateList
              testId="retrieval-datasets"
              title={`数据集 (${datasets.length})`}
              candidates={datasets}
              roleById={roleById}
              dimmed={dimmed}
              importedEid={importedEid}
              actionBusy={actionBusy}
              devMode={devMode}
              onAddEvidence={addToEvidence}
              onReject={markIrrelevant}
              onRetry={retrySimilar}
            />
            <CandidateList
              testId="retrieval-repos"
              title={`Repo (${repos.length})`}
              candidates={repos}
              roleById={roleById}
              dimmed={dimmed}
              importedEid={importedEid}
              actionBusy={actionBusy}
              devMode={devMode}
              onAddEvidence={addToEvidence}
              onReject={markIrrelevant}
              onRetry={retrySimilar}
            />
          </div>
        ) : null}

        {run ? (
          <div data-testid="retrieval-role-tabs">
            <Tabs
              testId="retrieval-role-tabs-root"
              defaultKey="baseline"
              items={[
                {
                  key: "baseline",
                  label: `Baseline (${baselinePapers.length})`,
                  content: (
                    <CandidateList
                      testId="retrieval-baseline"
                      title="Baseline 框架 / 方法"
                      candidates={baselinePapers}
                      roleById={roleById}
                      dimmed={dimmed}
                      importedEid={importedEid}
                      actionBusy={actionBusy}
                      devMode={devMode}
                      onAddEvidence={addToEvidence}
                      onAddLibrary={addToLibrary}
                      onReject={markIrrelevant}
                      onRetry={retrySimilar}
                    />
                  ),
                },
                {
                  key: "parallel",
                  label: `平行论文 (${parallelPapers.length})`,
                  content: (
                    <CandidateList
                      testId="retrieval-parallel"
                      title="平行应用论文"
                      candidates={parallelPapers}
                      roleById={roleById}
                      dimmed={dimmed}
                      importedEid={importedEid}
                      actionBusy={actionBusy}
                      devMode={devMode}
                      onAddEvidence={addToEvidence}
                      onAddLibrary={addToLibrary}
                      onReject={markIrrelevant}
                      onRetry={retrySimilar}
                    />
                  ),
                },
                {
                  key: "modules",
                  label: `模块论文 (${modulePapers.length})`,
                  content: (
                    <>
                      {modulePapers.length === 0 && (!moduleMatrix?.entries || moduleMatrix.entries.length === 0) ? (
                        <div className="pa-uw-zone">
                          <div className="pa-uw-zone__head">
                            <h3 className="pa-uw-zone__title">模块论文</h3>
                          </div>
                          <div className="pa-faint">暂无候选</div>
                        </div>
                      ) : (
                        <CandidateList
                          testId="retrieval-modules"
                          title="模块改进论文"
                          candidates={modulePapers}
                          roleById={roleById}
                          dimmed={dimmed}
                          importedEid={importedEid}
                          actionBusy={actionBusy}
                          devMode={devMode}
                          onAddEvidence={addToEvidence}
                          onAddLibrary={addToLibrary}
                          onReject={markIrrelevant}
                          onRetry={retrySimilar}
                        />
                      )}
                      {moduleMatrix && Array.isArray(moduleMatrix.entries) && moduleMatrix.entries.length > 0 ? (
                        <ModuleMatrixView matrix={moduleMatrix} />
                      ) : null}
                    </>
                  ),
                },
                {
                  key: "datasets",
                  label: `数据集 (${datasets.length + repos.length})`,
                  content: (
                    <div className="pa-uw-analysis-grid pa-uw-analysis-grid--double">
                      <CandidateList
                        testId="retrieval-datasets"
                        title={`数据集 (${datasets.length})`}
                        candidates={datasets}
                        roleById={roleById}
                        dimmed={dimmed}
                        importedEid={importedEid}
                        actionBusy={actionBusy}
                        devMode={devMode}
                        onAddEvidence={addToEvidence}
                        onReject={markIrrelevant}
                        onRetry={retrySimilar}
                      />
                      <CandidateList
                        testId="retrieval-repos"
                        title={`Repo (${repos.length})`}
                        candidates={repos}
                        roleById={roleById}
                        dimmed={dimmed}
                        importedEid={importedEid}
                        actionBusy={actionBusy}
                        devMode={devMode}
                        onAddEvidence={addToEvidence}
                        onReject={markIrrelevant}
                        onRetry={retrySimilar}
                      />
                    </div>
                  ),
                },
                ...(surveyPapers.length > 0
                  ? [
                      {
                        key: "survey",
                        label: `Survey (${surveyPapers.length})`,
                        content: (
                          <CandidateList
                            testId="retrieval-survey"
                            title="综述 (Survey — 仅背景)"
                            candidates={surveyPapers}
                            roleById={roleById}
                            dimmed={dimmed}
                            importedEid={importedEid}
                            actionBusy={actionBusy}
                            devMode={devMode}
                            onAddEvidence={addToEvidence}
                            onAddLibrary={addToLibrary}
                            onReject={markIrrelevant}
                            onRetry={retrySimilar}
                          />
                        ),
                      },
                    ]
                  : []),
                ...(devMode
                  ? [
                      {
                        key: "dev",
                        label: "开发者模式",
                        content: (
                          <DevPanel
                            run={run}
                            irrelevantPapers={irrelevantPapers}
                            roleById={roleById}
                            cleanSummary={cleanSummary}
                          />
                        ),
                      },
                    ]
                  : []),
              ]}
            />
          </div>
        ) : null}

        {run && run.gap_report && Array.isArray(run.gap_report.gaps) && run.gap_report.gaps.length > 0 ? (
          <div className="pa-uw-result-group" data-testid="retrieval-gap-report">
            <div className="pa-uw-result-group__title">缺口报告 (gap_report)</div>
            <ul className="pa-uw-result-list">
              {run.gap_report.gaps.map((g, i) => (
                <li
                  key={i}
                  className="pa-uw-result-item"
                  data-testid={`retrieval-gap-${i}`}
                >
                  <div className="pa-uw-result-item__head">
                    <strong>{g.topic ?? `gap ${i + 1}`}</strong>
                  </div>
                  {g.reason ? (
                    <div className="pa-uw-result-item__summary">{g.reason}</div>
                  ) : null}
                  {Array.isArray(g.next_step_queries) && g.next_step_queries.length > 0 ? (
                    <ul className="pa-checklist">
                      {g.next_step_queries.map((q, j) => (
                        <li key={`${i}-${j}`}>{q}</li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}

// ---------------- 子组件 ---------------- //

interface CandidateListProps {
  testId: string;
  title: string;
  candidates: RetrievalCandidate[];
  roleById: Map<string, RoleAssignment>;
  dimmed: Set<string>;
  importedEid: Map<string, string>;
  actionBusy: string | null;
  devMode: boolean;
  onAddEvidence: (c: RetrievalCandidate) => void;
  onAddLibrary?: (c: RetrievalCandidate) => void;
  onReject: (c: RetrievalCandidate) => void;
  onRetry: (c: RetrievalCandidate) => void;
}

function CandidateList({
  testId,
  title,
  candidates,
  roleById,
  dimmed,
  importedEid,
  actionBusy,
  devMode,
  onAddEvidence,
  onAddLibrary,
  onReject,
  onRetry,
}: CandidateListProps) {
  if (candidates.length === 0) {
    return (
      <div className="pa-uw-zone" data-testid={testId}>
        <div className="pa-uw-zone__head">
          <h3 className="pa-uw-zone__title">{title}</h3>
        </div>
        <div className="pa-faint">暂无候选</div>
      </div>
    );
  }
  return (
    <div className="pa-uw-zone" data-testid={testId}>
      <div className="pa-uw-zone__head">
        <h3 className="pa-uw-zone__title">{title}</h3>
      </div>
      <ul className="pa-uw-result-list">
        {candidates.map((c) => {
          const isDim = dimmed.has(c.candidate_id);
          const eid = importedEid.get(c.candidate_id);
          const role = roleById.get(c.candidate_id);
          return (
            <li
              key={c.candidate_id}
              className={`pa-uw-result-item ${isDim ? "pa-uw-result-item--dim" : ""}`}
              data-testid={`retrieval-${c.candidate_type}-${c.candidate_id}`}
            >
              <div className="pa-uw-result-item__head">
                <strong>{c.title}</strong>
                <Badge tone="info" testId={`retrieval-source-badge-${c.candidate_id}`}>
                  {c.source}
                </Badge>
                <Badge
                  tone={c.retrieval_score >= 0.5 ? "ok" : "neutral"}
                  testId={`retrieval-score-${c.candidate_id}`}
                >
                  score {c.retrieval_score.toFixed(2)}
                </Badge>
                {role ? (
                  <Badge tone="neutral" testId={`retrieval-role-badge-${c.candidate_id}`}>
                    {ROLE_LABELS[role.role]}
                  </Badge>
                ) : null}
              </div>
              <div className="pa-uw-result-item__meta">
                {c.year ?? "—"} · {c.authors.slice(0, 3).join(", ") || "—"}
                {c.citation_count != null ? ` · cited ${c.citation_count}` : ""}
                {c.stars != null ? ` · ★${c.stars}` : ""}
              </div>
              {c.abstract ? (
                <div className="pa-uw-result-item__summary">
                  {c.abstract.length > 160 ? `${c.abstract.slice(0, 160)}...` : c.abstract}
                </div>
              ) : null}
              {devMode && role ? (
                <div className="pa-uw-result-item__meta" data-testid={`retrieval-role-detail-${c.candidate_id}`}>
                  {role.base_framework ? `base=${role.base_framework} · ` : ""}
                  {role.modules_added && role.modules_added.length > 0
                    ? `modules=[${role.modules_added.join(", ")}] · `
                    : ""}
                  {role.reason ? `reason=${role.reason.slice(0, 60)}` : ""}
                </div>
              ) : null}
              {c.url ? (
                <a className="pa-link" href={c.url} target="_blank" rel="noreferrer">
                  打开链接
                </a>
              ) : null}
              {eid ? (
                <div
                  className="pa-small pa-muted"
                  data-testid={`retrieval-imported-id-${c.candidate_id}`}
                >
                  evidence_id: {eid}
                </div>
              ) : null}
              <div className="pa-uw-library-item__actions">
                <button
                  type="button"
                  className="pa-btn pa-btn--primary pa-btn--sm"
                  onClick={() => onAddEvidence(c)}
                  disabled={actionBusy === `evidence-${c.candidate_id}`}
                  data-testid={`retrieval-add-evidence-${c.candidate_id}`}
                >
                  {actionBusy === `evidence-${c.candidate_id}` ? "导入中..." : "加入证据"}
                </button>
                {onAddLibrary && c.candidate_type === "paper" ? (
                  <button
                    type="button"
                    className="pa-btn pa-btn--secondary pa-btn--sm"
                    onClick={() => onAddLibrary(c)}
                    disabled={actionBusy === `library-${c.candidate_id}`}
                    data-testid={`retrieval-add-library-${c.candidate_id}`}
                  >
                    {actionBusy === `library-${c.candidate_id}` ? "入库中..." : "加入文献库"}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="pa-btn pa-btn--ghost pa-btn--sm"
                  onClick={() => onReject(c)}
                  disabled={isDim}
                  data-testid={`retrieval-reject-${c.candidate_id}`}
                >
                  {isDim ? "已标记" : "标记不相关"}
                </button>
                <button
                  type="button"
                  className="pa-btn pa-btn--ghost pa-btn--sm"
                  onClick={() => onRetry(c)}
                  data-testid={`retrieval-retry-similar-${c.candidate_id}`}
                >
                  补搜类似
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ---------------- 模块矩阵视图 ---------------- //

interface ModuleMatrixViewProps {
  matrix: ModuleMatrix;
}

function ModuleMatrixView({ matrix }: ModuleMatrixViewProps) {
  return (
    <div className="pa-uw-zone" data-testid="retrieval-module-matrix">
      <div className="pa-uw-zone__head">
        <h3 className="pa-uw-zone__title">模块矩阵 (Base + Module 组合)</h3>
        <div className="pa-uw-zone__meta">
          {matrix.topic ? `topic=${matrix.topic}` : ""}
          {matrix.domain ? ` · domain=${matrix.domain}` : ""}
        </div>
      </div>
      {Array.isArray(matrix.entries) && matrix.entries.length > 0 ? (
        <table className="pa-table pa-table--compact">
          <thead>
            <tr>
              <th>Base</th>
              <th>Module A</th>
              <th>Module B</th>
              <th>Dataset</th>
              <th>Metrics</th>
              <th>Improvement</th>
            </tr>
          </thead>
          <tbody>
            {matrix.entries.map((e, i) => (
              <tr key={i} data-testid={`retrieval-module-row-${i}`}>
                <td>{e.base ?? "—"}</td>
                <td>{e.module_a ?? "—"}</td>
                <td>{e.module_b ?? "—"}</td>
                <td>{e.dataset ?? "—"}</td>
                <td>
                  {Array.isArray(e.metrics) && e.metrics.length > 0
                    ? e.metrics.join(", ")
                    : "—"}
                </td>
                <td>{e.improvement_description ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {Array.isArray(matrix.missing_module_types) && matrix.missing_module_types.length > 0 ? (
        <div className="pa-uw-result-item__summary" data-testid="retrieval-module-missing">
          缺失模块类型: {matrix.missing_module_types.join(", ")}
        </div>
      ) : null}
    </div>
  );
}

// ---------------- 开发者模式面板 ---------------- //

interface DevPanelProps {
  run: RetrievalRun;
  irrelevantPapers: RetrievalCandidate[];
  roleById: Map<string, RoleAssignment>;
  cleanSummary: Record<string, number> | null;
}

function DevPanel({ run, irrelevantPapers, roleById, cleanSummary }: DevPanelProps) {
  return (
    <div className="pa-uw-zone" data-testid="retrieval-dev-panel">
      <div className="pa-uw-zone__head">
        <h3 className="pa-uw-zone__title">开发者模式 — 过滤 / 清洗 / 轨迹</h3>
      </div>

      <div className="pa-uw-result-group" data-testid="retrieval-clean-summary">
        <div className="pa-uw-result-group__title">清洗状态汇总 (clean_summary)</div>
        {cleanSummary && Object.keys(cleanSummary).length > 0 ? (
          <ul className="pa-uw-result-list">
            {Object.entries(cleanSummary).map(([k, v]) => (
              <li key={k} className="pa-uw-result-item">
                <strong>{k}</strong>
                <span className="pa-muted">: {v}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="pa-faint">后端未返回 clean_summary (旧版本或未启用清洗)</div>
        )}
      </div>

      <div className="pa-uw-result-group" data-testid="retrieval-irrelevant-section">
        <div className="pa-uw-result-group__title">不相关候选 (role=irrelevant)</div>
        {irrelevantPapers.length === 0 ? (
          <div className="pa-faint">无</div>
        ) : (
          <ul className="pa-uw-result-list">
            {irrelevantPapers.map((c) => {
              const role = roleById.get(c.candidate_id);
              return (
                <li
                  key={c.candidate_id}
                  className="pa-uw-result-item"
                  data-testid={`retrieval-irrelevant-${c.candidate_id}`}
                >
                  <div className="pa-uw-result-item__head">
                    <strong>{c.title}</strong>
                    <Badge tone="info">{c.source}</Badge>
                    <Badge tone="neutral">score {c.retrieval_score.toFixed(2)}</Badge>
                  </div>
                  {role?.reason ? (
                    <div className="pa-uw-result-item__summary">reason: {role.reason}</div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="pa-uw-result-group" data-testid="retrieval-source-trace">
        <div className="pa-uw-result-group__title">来源轨迹 (原始分数 / 候选数)</div>
        <ul className="pa-uw-result-list">
          {run.source_results.map((sr) => (
            <li key={sr.source} className="pa-uw-result-item">
              <strong>{sr.source}</strong>: status={sr.status} · {sr.candidate_count} candidates · {sr.duration_ms}ms
              {sr.error ? ` · err=${sr.error}` : ""}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}