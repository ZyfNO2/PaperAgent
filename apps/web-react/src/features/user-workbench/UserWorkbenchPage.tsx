import { useMemo, useState } from "react";
import { apiClient, ApiError } from "../../app/apiClient";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { EvidenceSubmitPanel } from "../evidence/EvidenceSubmitPanel";
import { PaperLibraryEditor } from "../paper-library/PaperLibraryEditor";
import { LocalRagAskPanel } from "../paper-library/LocalRagAskPanel";
import { TopicIntake } from "../step-workbench/components/TopicIntake";
import { WorkbenchChat } from "../step-workbench/components/WorkbenchChat";
import type { CommandPreview } from "../step-workbench/stepWorkbenchReducer";
import type { ChatMessage } from "../step-workbench/stepTypes";

const QUICK_ACTIONS = [
  { key: "modify", label: "修改题目", text: "请把题目改为: " },
  { key: "constraint", label: "补充约束", text: "补充约束: " },
  { key: "retrieve", label: "让 AI 查证据", text: "请帮我查证 " },
  { key: "next", label: "生成下一步建议", text: "请给我下一步建议" },
] as const;

const NOTES_KEY = "paperagent:notes";

interface TopicUnderstanding {
  raw_topic: string;
  normalized_topic: string;
  intent_zh: string;
  is_specific_object: boolean;
}

interface KeywordBreakdown {
  method_keywords: string[];
  task_keywords: string[];
  object_keywords: string[];
  scenario_keywords: string[];
  metric_keywords: string[];
  risk_terms: string[];
  query_keywords_zh: string[];
  query_keywords_en: string[];
}

interface EvidenceRef {
  evidence_id: string;
  evidence_type: string;
  title: string;
  reason: string;
  role: string;
  score?: number | null;
  review_status?: string;
  url?: string | null;
}

interface PaperHit {
  paper_id: string;
  title: string;
  year?: number | null;
  url?: string | null;
  source?: string;
  relevance_score?: number | null;
  summary_zh?: string | null;
}

interface DatasetHit {
  dataset_id: string;
  name: string;
  download?: string | null;
  fit?: string;
  quality_score?: number | null;
  dataset_status?: string | null;
}

interface BaselineHit {
  baseline_id: string;
  name: string;
  repository_url?: string | null;
  quality_score?: number | null;
  repo_type?: string | null;
}

interface EvidenceSummary {
  papers: PaperHit[];
  datasets: DatasetHit[];
  baselines: BaselineHit[];
  metrics: string[];
  paper_count: number;
  dataset_count: number;
  baseline_count: number;
  has_public_dataset: boolean;
  has_repro_baseline: boolean;
}

interface WorkPackageSuggestion {
  wp_id: string;
  title: string;
  research_question: string;
  method_approach: string;
  data_source: string;
  experiment_plan: string;
  chapter: string;
  open_questions: string[];
  status: string;
}

interface PivotRoute {
  level: string;
  new_topic: string;
  tradeoff: string;
}

interface ProposalRecommendation {
  recommended_topic: string;
  recommendation_reason: string[];
  work_packages: WorkPackageSuggestion[];
  proposal_outline: string[];
  pivot_routes: PivotRoute[];
}

interface ReviewCheck {
  dimension: string;
  result: string;
  comment: string;
}

interface LightReview {
  verdict: string;
  summary: string;
  checks: ReviewCheck[];
  revision_checklist: string[];
}

interface FeasibilitySummary {
  verdict: string;
  reason: string;
  paper_status: string;
  dataset_status: string;
  baseline_status: string;
  engineering_status: string;
  missing_evidence: string[];
  recommended_next_action: string;
  evidence_refs: EvidenceRef[];
  blocking_refs: EvidenceRef[];
  confidence: number;
}

interface AnalyzeResponse {
  project_id: string;
  topic_understanding: TopicUnderstanding;
  keyword_breakdown: KeywordBreakdown;
  evidence_summary: EvidenceSummary;
  feasibility: FeasibilitySummary;
  proposal_recommendation: ProposalRecommendation;
  light_review: LightReview;
}

function loadNotes(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(NOTES_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function saveNotes(notes: string[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(NOTES_KEY, JSON.stringify(notes));
}

function compactList(...groups: Array<string[] | undefined>): string[] {
  return groups.flatMap((group) => group ?? []).filter(Boolean);
}

function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.body === "string") return error.body;
    if (error.body && typeof error.body === "object") {
      return JSON.stringify(error.body, null, 2);
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "未知错误";
}

function scoreText(score?: number | null): string | null {
  if (typeof score !== "number") return null;
  return score.toFixed(2);
}

function stripPrefix(text: string, patterns: RegExp[]): string {
  let output = text;
  for (const pattern of patterns) {
    output = output.replace(pattern, "");
  }
  return output.trim();
}

function buildRetrieveReply(analysis: AnalyzeResponse): string {
  const paperTitles = analysis.evidence_summary.papers.slice(0, 2).map((item) => item.title);
  const datasetNames = analysis.evidence_summary.datasets.slice(0, 2).map((item) => item.name);
  const repoNames = analysis.evidence_summary.baselines.slice(0, 2).map((item) => item.name);
  const lines = [
    `我已经找到 ${analysis.evidence_summary.paper_count} 篇论文、${analysis.evidence_summary.dataset_count} 个数据集、${analysis.evidence_summary.baseline_count} 个 baseline。`,
  ];
  if (paperTitles.length) lines.push(`论文优先看：${paperTitles.join(" / ")}`);
  if (datasetNames.length) lines.push(`数据集优先看：${datasetNames.join(" / ")}`);
  if (repoNames.length) lines.push(`工程 baseline：${repoNames.join(" / ")}`);
  if (analysis.feasibility.missing_evidence.length) {
    lines.push(`当前还缺：${analysis.feasibility.missing_evidence.join("；")}`);
  }
  return lines.join("\n");
}

function buildNextStepReply(analysis: AnalyzeResponse): string {
  const outline = analysis.proposal_recommendation.proposal_outline.slice(0, 3);
  const checklist = analysis.light_review.revision_checklist.slice(0, 3);
  const lines = [
    `当前可行性：${analysis.feasibility.verdict}。${analysis.feasibility.recommended_next_action}`,
  ];
  if (outline.length) lines.push(`建议先推进：${outline.join(" / ")}`);
  if (checklist.length) lines.push(`优先补齐：${checklist.join("；")}`);
  return lines.join("\n");
}

function AnalysisError({ error }: { error: string }) {
  return (
    <Card title="分析失败" testId="uw-analysis-error">
      <div className="pa-error-card__summary">后端分析未返回可用结果，请先检查输入或后端状态。</div>
      <pre className="pa-error-card__debug">{error}</pre>
    </Card>
  );
}

function KeywordGroup({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="pa-uw-result-group">
      <div className="pa-uw-result-group__title">{title}</div>
      <div className="pa-uw-chip-row">
        {items.map((item) => (
          <span key={`${title}-${item}`} className="pa-uw-chip">
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function EvidenceList({
  title,
  items,
}: {
  title: string;
  items: Array<{
    id: string;
    name: string;
    href?: string | null;
    score?: number | null;
    meta?: string[];
    summary?: string | null;
  }>;
}) {
  return (
    <Card title={title}>
      {items.length === 0 ? (
        <div className="pa-faint">暂无结果</div>
      ) : (
        <ul className="pa-uw-result-list">
          {items.map((item) => (
            <li key={item.id} className="pa-uw-result-item">
              <div className="pa-uw-result-item__head">
                <strong>{item.name}</strong>
                {scoreText(item.score) ? (
                  <Badge tone="info">score {scoreText(item.score)}</Badge>
                ) : null}
              </div>
              {item.meta && item.meta.length ? (
                <div className="pa-uw-result-item__meta">{item.meta.join(" / ")}</div>
              ) : null}
              {item.summary ? <div className="pa-uw-result-item__summary">{item.summary}</div> : null}
              {item.href ? (
                <a href={item.href} target="_blank" rel="noreferrer" className="pa-link">
                  打开链接
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function AnalysisResults({ analysis }: { analysis: AnalyzeResponse }) {
  const keyword = analysis.keyword_breakdown;
  const topEvidence = analysis.feasibility.evidence_refs.slice(0, 4);
  return (
    <div className="pa-uw-analysis" data-testid="uw-analysis-results">
      <div className="pa-uw-analysis-grid">
        <Card title="题目理解" testId="uw-topic-understanding">
          <div className="pa-uw-kv">
            <div>
              <span className="pa-faint">规范题目</span>
              <div>{analysis.topic_understanding.normalized_topic}</div>
            </div>
            <div>
              <span className="pa-faint">是否已指向具体对象</span>
              <div>{analysis.topic_understanding.is_specific_object ? "是" : "否"}</div>
            </div>
          </div>
          <p className="pa-uw-paragraph">{analysis.topic_understanding.intent_zh}</p>
        </Card>

        <Card title="可行性判断" testId="uw-feasibility">
          <div className="pa-uw-result-item__head">
            <strong>{analysis.feasibility.verdict}</strong>
            <Badge tone={analysis.feasibility.verdict.includes("不") ? "err" : analysis.feasibility.verdict.includes("可转") ? "warn" : "ok"}>
              confidence {analysis.feasibility.confidence.toFixed(2)}
            </Badge>
          </div>
          <p className="pa-uw-paragraph">{analysis.feasibility.reason}</p>
          <div className="pa-uw-kv pa-uw-kv--stack">
            <div>论文：{analysis.feasibility.paper_status}</div>
            <div>数据集：{analysis.feasibility.dataset_status}</div>
            <div>Baseline：{analysis.feasibility.baseline_status}</div>
            <div>工程：{analysis.feasibility.engineering_status}</div>
          </div>
          {analysis.feasibility.missing_evidence.length ? (
            <ul className="pa-uw-checklist">
              {analysis.feasibility.missing_evidence.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
        </Card>
      </div>

      <Card title="关键词拆解" testId="uw-keywords">
        <KeywordGroup title="方法词" items={keyword.method_keywords} />
        <KeywordGroup title="任务词" items={keyword.task_keywords} />
        <KeywordGroup title="对象词" items={keyword.object_keywords} />
        <KeywordGroup title="场景词" items={keyword.scenario_keywords} />
        <KeywordGroup title="指标词" items={keyword.metric_keywords} />
        <KeywordGroup title="风险词" items={keyword.risk_terms} />
        <KeywordGroup title="中文检索词" items={keyword.query_keywords_zh} />
        <KeywordGroup title="英文检索词" items={keyword.query_keywords_en} />
      </Card>

      <div className="pa-uw-analysis-grid pa-uw-analysis-grid--triple">
        <EvidenceList
          title={`论文候选 (${analysis.evidence_summary.paper_count})`}
          items={analysis.evidence_summary.papers.map((item) => ({
            id: item.paper_id,
            name: item.title,
            href: item.url,
            score: item.relevance_score,
            meta: compactList(
              item.year ? [String(item.year)] : undefined,
              item.source ? [item.source] : undefined,
            ),
            summary: item.summary_zh ?? null,
          }))}
        />
        <EvidenceList
          title={`数据集候选 (${analysis.evidence_summary.dataset_count})`}
          items={analysis.evidence_summary.datasets.map((item) => ({
            id: item.dataset_id,
            name: item.name,
            href: item.download,
            score: item.quality_score,
            meta: compactList(item.fit ? [`fit ${item.fit}`] : undefined, item.dataset_status ? [item.dataset_status] : undefined),
          }))}
        />
        <EvidenceList
          title={`Baseline / Repo (${analysis.evidence_summary.baseline_count})`}
          items={analysis.evidence_summary.baselines.map((item) => ({
            id: item.baseline_id,
            name: item.name,
            href: item.repository_url,
            score: item.quality_score,
            meta: compactList(item.repo_type ? [item.repo_type] : undefined),
          }))}
        />
      </div>

      <div className="pa-uw-analysis-grid">
        <Card title="开题解析 / 题目推荐" testId="uw-proposal-recommendation">
          <div className="pa-uw-result-item__head">
            <strong>{analysis.proposal_recommendation.recommended_topic}</strong>
          </div>
          {analysis.proposal_recommendation.recommendation_reason.length ? (
            <ul className="pa-uw-checklist">
              {analysis.proposal_recommendation.recommendation_reason.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
          {analysis.proposal_recommendation.proposal_outline.length ? (
            <>
              <div className="pa-uw-result-group__title">开题结构建议</div>
              <ol className="pa-uw-number-list">
                {analysis.proposal_recommendation.proposal_outline.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ol>
            </>
          ) : null}
        </Card>

        <Card title="低门槛审核" testId="uw-light-review">
          <div className="pa-uw-result-item__head">
            <strong>{analysis.light_review.verdict}</strong>
          </div>
          <p className="pa-uw-paragraph">{analysis.light_review.summary}</p>
          <ul className="pa-uw-checklist">
            {analysis.light_review.checks.map((item) => (
              <li key={`${item.dimension}-${item.result}`}>
                <strong>{item.dimension}</strong>：{item.result}，{item.comment}
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="pa-uw-analysis-grid">
        <Card title="工作包建议" testId="uw-work-packages">
          {analysis.proposal_recommendation.work_packages.length === 0 ? (
            <div className="pa-faint">暂无工作包</div>
          ) : (
            <div className="pa-uw-package-list">
              {analysis.proposal_recommendation.work_packages.map((item) => (
                <div key={item.wp_id} className="pa-uw-package">
                  <div className="pa-uw-result-item__head">
                    <strong>{item.title}</strong>
                    <Badge tone={item.status === "ready" ? "ok" : "warn"}>{item.status}</Badge>
                  </div>
                  <div className="pa-uw-package__line"><span className="pa-faint">研究问题</span>{item.research_question}</div>
                  <div className="pa-uw-package__line"><span className="pa-faint">方法路线</span>{item.method_approach}</div>
                  <div className="pa-uw-package__line"><span className="pa-faint">数据来源</span>{item.data_source}</div>
                  <div className="pa-uw-package__line"><span className="pa-faint">实验计划</span>{item.experiment_plan}</div>
                  <div className="pa-uw-package__line"><span className="pa-faint">章节</span>{item.chapter}</div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="退化 / 转向路线" testId="uw-pivot-routes">
          {analysis.proposal_recommendation.pivot_routes.length === 0 ? (
            <div className="pa-faint">暂无退化路线</div>
          ) : (
            <div className="pa-uw-package-list">
              {analysis.proposal_recommendation.pivot_routes.map((item) => (
                <div key={`${item.level}-${item.new_topic}`} className="pa-uw-package">
                  <div className="pa-uw-result-item__head">
                    <strong>{item.level}</strong>
                    <Badge tone="info">{item.new_topic}</Badge>
                  </div>
                  <div className="pa-uw-package__line">{item.tradeoff}</div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card title="关键证据引用" testId="uw-evidence-refs">
        {topEvidence.length === 0 ? (
          <div className="pa-faint">暂无关键证据</div>
        ) : (
          <ul className="pa-uw-result-list">
            {topEvidence.map((item) => (
              <li key={item.evidence_id} className="pa-uw-result-item">
                <div className="pa-uw-result-item__head">
                  <strong>{item.title}</strong>
                  <Badge tone={item.role === "warns" ? "warn" : "info"}>{item.role}</Badge>
                </div>
                <div className="pa-uw-result-item__meta">
                  {item.evidence_type} / {item.review_status ?? "unreviewed"}
                  {scoreText(item.score) ? ` / score ${scoreText(item.score)}` : ""}
                </div>
                <div className="pa-uw-result-item__summary">{item.reason}</div>
                {item.url ? (
                  <a href={item.url} target="_blank" rel="noreferrer" className="pa-link">
                    打开链接
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export interface UserWorkbenchPageProps {
  testId?: string;
}

export function UserWorkbenchPage({ testId }: UserWorkbenchPageProps) {
  const [topicInput, setTopicInput] = useState("");
  const [topic, setTopic] = useState("");
  const [status, setStatus] = useState<"尚未开始" | "正在分析" | "等待确认" | "已确认">("尚未开始");
  const [notes, setNotes] = useState<string[]>(() => loadNotes());
  const [chatDraft, setChatDraft] = useState("");
  const [chatPreview, setChatPreview] = useState<CommandPreview | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const statusTone = useMemo(() => {
    if (status === "已确认") return "ok";
    if (status === "尚未开始") return "neutral";
    return "info";
  }, [status]);

  function pushMsg(role: ChatMessage["role"], text: string) {
    setMessages((prev) => [
      ...prev,
      {
        id: `${role[0]}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        role,
        text,
        ts: Date.now(),
      },
    ]);
  }

  function pushAssistant(text: string) {
    pushMsg("assistant", text);
  }

  function pushSystem(text: string) {
    pushMsg("system", text);
  }

  async function onStart() {
    const nextTopic = topicInput.trim();
    if (!nextTopic || loading) return;
    setTopic(nextTopic);
    setStatus("正在分析");
    setLoading(true);
    setAnalysisError(null);

    try {
      const resp = await apiClient.post<AnalyzeResponse>("/api/v1/one-topic/analyze", {
        raw_topic: nextTopic,
        prefer: "heuristic",
      });
      setAnalysis(resp);
      setStatus("等待确认");
      pushAssistant(
        `我已经完成题目理解、关键词拆解、资料检索和开题初判。当前结论是：${resp.feasibility.verdict}。`,
      );
    } catch (error) {
      setAnalysis(null);
      setAnalysisError(formatError(error));
      setStatus("尚未开始");
      pushSystem("后端分析失败，请先检查接口状态或输入格式。");
    } finally {
      setLoading(false);
    }
  }

  function submitChat(text: string) {
    const nextText = text.trim();
    if (!nextText) return;
    pushMsg("user", nextText);
    setChatDraft("");

    if (/^(修改|改成|改为|更新)/.test(nextText)) {
      setChatPreview({
        kind: "set_topic",
        intent: "修改题目",
        description: stripPrefix(nextText, [/^(修改|改成|改为|更新)\s*/]),
      });
      return;
    }

    if (/^(补充|加上|添加约束)/.test(nextText)) {
      const payload = stripPrefix(nextText, [/^(补充|加上|添加约束)\s*/]);
      setChatPreview({
        kind: "add_note",
        intent: "补充约束",
        description: payload,
        payload,
      });
      return;
    }

    if (/(让\s*AI\s*查|请(?:帮我)?查(?:证|找)?|检索|查询)/i.test(nextText)) {
      if (!analysis) {
        pushAssistant("请先点击“开始分析”，我才能基于真实后端结果继续给你找资料。");
      } else {
        pushAssistant(buildRetrieveReply(analysis));
      }
      setChatPreview(null);
      return;
    }

    if (/下一步建议|下一步/.test(nextText)) {
      if (!analysis) {
        pushAssistant("请先完成一次分析，我再根据后端结果给你下一步建议。");
      } else {
        pushAssistant(buildNextStepReply(analysis));
      }
      setChatPreview(null);
      return;
    }

    setChatPreview({
      kind: "unsupported",
      intent: "未识别指令",
      description: `当前只支持：修改题目 / 补充约束 / 查证据 / 下一步建议。`,
    });
  }

  function applyPreview() {
    if (!chatPreview) return;

    if (chatPreview.kind === "set_topic") {
      setTopic(chatPreview.description);
      setTopicInput(chatPreview.description);
      setAnalysis(null);
      setAnalysisError(null);
      setStatus("尚未开始");
      pushSystem(`题目已更新为：${chatPreview.description}。请重新点击“开始分析”。`);
    } else if (chatPreview.kind === "add_note") {
      const note = chatPreview.payload ?? chatPreview.description;
      const nextNotes = [...notes, note];
      setNotes(nextNotes);
      saveNotes(nextNotes);
      pushSystem(`已添加约束：${note}`);
    } else {
      pushSystem(chatPreview.description);
    }

    setChatPreview(null);
  }

  return (
    <div className="pa-uw" data-testid={testId ?? "user-workbench"}>
      <header className="pa-uw-header" data-testid="uw-header">
        <h1 className="pa-uw-title">选题与开题工作台</h1>
        <p className="pa-uw-sub">输入题目，与 AI 讨论，提交证据，维护文献库。</p>
      </header>

      <div className="pa-uw-layout" data-testid="uw-layout">
        <aside className="pa-uw-sidebar">
          <section className="pa-uw-zone pa-uw-zone--b" data-testid="uw-zone-b">
            <header className="pa-uw-zone__head">
              <span className="pa-uw-zone__cap">B</span>
              <h2 className="pa-uw-zone__title">与 AI 的交互</h2>
            </header>
            <div className="pa-uw-zone__body pa-uw-zone__body--b">
              <div className="pa-uw-quick">
                {QUICK_ACTIONS.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    className="pa-btn pa-btn--secondary pa-btn--sm"
                    onClick={() => setChatDraft(item.text)}
                    data-testid={`uw-quick-${item.key}`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <WorkbenchChat
                draft={chatDraft}
                preview={chatPreview}
                messages={messages}
                onDraftChange={setChatDraft}
                onSubmit={submitChat}
                onAcceptPreview={applyPreview}
                testId="uw-chat"
              />
            </div>
          </section>
        </aside>

        <main className="pa-uw-main">
          <section className="pa-uw-zone pa-uw-zone--a" data-testid="uw-zone-a">
            <header className="pa-uw-zone__head">
              <span className="pa-uw-zone__cap">A</span>
              <h2 className="pa-uw-zone__title">题目输入</h2>
              <span className={`pa-uw-zone__status pa-uw-zone__status--${statusTone}`} data-testid="uw-topic-status">
                {status}
              </span>
            </header>
            <div className="pa-uw-zone__body">
              <TopicIntake
                topicInput={topicInput}
                topic={topic}
                notes={notes}
                onTopicInputChange={setTopicInput}
                onStart={onStart}
                testId="uw-topic-intake"
              />
              {loading ? <div className="pa-faint">正在调用后端分析，请稍等…</div> : null}
              {analysis ? (
                <div className="pa-small pa-muted" data-testid="uw-project-id">
                  project_id: {analysis.project_id}
                </div>
              ) : null}
            </div>
          </section>

          {analysisError ? <AnalysisError error={analysisError} /> : null}
          {analysis ? <AnalysisResults analysis={analysis} /> : null}

          <div className="pa-uw-grid" data-testid="uw-grid-cd">
            <EvidenceSubmitPanel testId="uw-evidence" />
            <PaperLibraryEditor testId="uw-library" />
            <LocalRagAskPanel testId="uw-local-rag" />
          </div>
        </main>
      </div>
    </div>
  );
}
