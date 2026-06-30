import { useMemo, useState } from "react";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { EvidenceSubmitPanel } from "../evidence/EvidenceSubmitPanel";
import { RetrievalCandidatePanel } from "../evidence/RetrievalCandidatePanel";
import { PaperLibraryEditor } from "../paper-library/PaperLibraryEditor";
import { LocalRagAskPanel } from "../paper-library/LocalRagAskPanel";
import { TopicIntake } from "../step-workbench/components/TopicIntake";
import { WorkbenchChat } from "../step-workbench/components/WorkbenchChat";
import { DirectionDecisionPanel } from "../graduation-direction/DirectionDecisionPanel";
import type { CommandPreview } from "../step-workbench/stepWorkbenchReducer";
import type { ChatMessage } from "../step-workbench/stepTypes";

const QUICK_ACTIONS = [
  { key: "modify", label: "修改题目", text: "请把题目改为: " },
  { key: "constraint", label: "补充约束", text: "补充约束: " },
  { key: "retrieve", label: "让 AI 查证据", text: "请帮我查证 " },
  { key: "next", label: "生成下一步建议", text: "请给我下一步建议" },
] as const;

const NOTES_KEY = "paperagent:notes";

// ponytail: Session 66 T1-T3 — new main flow replaces legacy one-shot /analyze.
// T1-T3 covers only the state skeleton + the first transition (idle -> keywords_review).
// Retrieval / baseline / work-advice endpoints come in T4+.
type MainFlowStep =
  | "idle"
  | "keywords_review"
  | "retrieval_review"
  | "baseline_select"
  | "work_advice"
  | "stopped";

interface ParsedKeywords {
  method_keywords: string[];
  task_keywords: string[];
  object_keywords: string[];
  scenario_keywords: string[];
  metric_keywords: string[];
  risk_terms: string[];
  query_keywords_zh: string[];
  query_keywords_en: string[];
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

function stripPrefix(text: string, patterns: RegExp[]): string {
  let output = text;
  for (const pattern of patterns) {
    output = output.replace(pattern, "");
  }
  return output.trim();
}

export interface UserWorkbenchPageProps {
  testId?: string;
}

export function UserWorkbenchPage({ testId }: UserWorkbenchPageProps) {
  const [topicInput, setTopicInput] = useState("");
  const [topic, setTopic] = useState("");
  const [notes, setNotes] = useState<string[]>(() => loadNotes());
  const [chatDraft, setChatDraft] = useState("");
  const [chatPreview, setChatPreview] = useState<CommandPreview | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // ponytail: Session 66 T1-T3 — replace legacy one-shot analysis state.
  const [flowStep, setFlowStep] = useState<MainFlowStep>("idle");
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [keywords, setKeywords] = useState<ParsedKeywords | null>(null);
  const [loading, setLoading] = useState(false);
  const [flowError, setFlowError] = useState<string | null>(null);

  const statusLabel = useMemo(() => {
    if (flowStep === "idle") return "尚未开始";
    if (flowStep === "keywords_review") return "等待确认关键词";
    if (flowStep === "retrieval_review") return "等待确认检索";
    if (flowStep === "baseline_select") return "等待选择基线";
    if (flowStep === "work_advice") return "等待确认工作建议";
    return "已停止";
  }, [flowStep]);

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

  // ponytail: Session 66 T1-T3 stub — keywords endpoint arrives in T4.
  // For now: transition to keywords_review with an empty skeleton so the UI compiles.
  async function onStart() {
    const nextTopic = topicInput.trim();
    if (!nextTopic || loading) return;
    setTopic(nextTopic);
    setLoading(true);
    setFlowError(null);

    try {
      // TODO(Phase 66 T4): replace with POST /api/v1/keywords (LLM + heuristic fallback).
      setKeywords({
        method_keywords: [],
        task_keywords: [],
        object_keywords: [],
        scenario_keywords: [],
        metric_keywords: [],
        risk_terms: [],
        query_keywords_zh: [],
        query_keywords_en: [],
      });
      setActiveProjectId(null);
      setFlowStep("keywords_review");
      pushAssistant(`已收到题目：「${nextTopic}」。等待关键词拆解完成后进入确认环节。`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "未知错误";
      setFlowError(message);
      setFlowStep("idle");
      pushSystem(`启动失败：${message}`);
    } finally {
      setLoading(false);
    }
  }

  function removeKeyword(group: keyof ParsedKeywords, index: number) {
    if (!keywords) return;
    const nextList = [...keywords[group]];
    nextList.splice(index, 1);
    setKeywords({ ...keywords, [group]: nextList });
  }

  function renderKeywordGroup(group: keyof ParsedKeywords, label: string) {
    if (!keywords) return null;
    const items = keywords[group];
    if (!items.length) return null;
    return (
      <div className="pa-uw-result-group" key={group}>
        <div className="pa-uw-result-group__title">{label}</div>
        <div className="pa-uw-chip-row">
          {items.map((item, idx) => (
            <span key={`${group}-${idx}-${item}`} className="pa-uw-chip pa-uw-chip--removable">
              {item}
              <button
                type="button"
                className="pa-uw-chip__remove"
                aria-label={`删除 ${item}`}
                onClick={() => removeKeyword(group, idx)}
                data-testid={`uw-kw-remove-${group}-${idx}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </div>
    );
  }

  function renderKeywordsReview() {
    if (!keywords) return null;
    return (
      <Card title="关键词确认" testId="uw-keywords-confirm">
        {renderKeywordGroup("method_keywords", "方法词")}
        {renderKeywordGroup("task_keywords", "任务词")}
        {renderKeywordGroup("object_keywords", "对象词")}
        {renderKeywordGroup("scenario_keywords", "场景词")}
        {renderKeywordGroup("metric_keywords", "指标词")}
        {renderKeywordGroup("risk_terms", "风险词")}
        <div className="pa-faint pa-uw-direction__note">
          T4+ 接入关键词确认后的检索 / 基线 / 工作建议流程。
        </div>
      </Card>
    );
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

    // ponytail: legacy "查证据 / 下一步建议" paths removed with /one-topic/analyze.
    // T4+ will wire these to the new retrieval / work-advice endpoints.
    setChatPreview({
      kind: "unsupported",
      intent: "未识别指令",
      description: "当前只支持：修改题目 / 补充约束。查证据 / 下一步建议将在 T4+ 接入。",
    });
  }

  function applyPreview() {
    if (!chatPreview) return;

    if (chatPreview.kind === "set_topic") {
      setTopic(chatPreview.description);
      setTopicInput(chatPreview.description);
      setFlowStep("idle");
      setKeywords(null);
      setActiveProjectId(null);
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
              <Badge tone="warn" testId="uw-zone-b-partial-badge">
                部分实现
              </Badge>
            </header>
            <div className="pa-uw-zone__body pa-uw-zone__body--b">
              <div
                className="pa-uw-zone__hint"
                data-testid="uw-zone-b-partial-hint"
                title="当前支持：修改题目 / 补充约束。查证据 / 下一步建议将在 Phase 66 后续任务接入。"
              >
                当前支持：修改题目 / 补充约束。查证据 / 下一步建议将在 Phase 66 后续任务接入。
              </div>
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
              <span
                className={`pa-uw-zone__status pa-uw-zone__status--info`}
                data-testid="uw-topic-status"
              >
                {statusLabel}
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
              {loading ? <div className="pa-faint">正在调用后端，请稍等…</div> : null}
              {activeProjectId ? (
                <div className="pa-small pa-muted" data-testid="uw-project-id">
                  project_id: {activeProjectId}
                </div>
              ) : null}
              {flowError ? (
                <Card title="启动失败" testId="uw-flow-error">
                  <pre className="pa-error-card__debug">{flowError}</pre>
                </Card>
              ) : null}
            </div>
          </section>

          {flowStep === "keywords_review" ? renderKeywordsReview() : null}

          <RetrievalCandidatePanel
            testId="uw-retrieval"
            topic={topic}
          />

          <DirectionDecisionPanel
            testId="uw-direction-panel"
            topic={topic}
            projectId={activeProjectId}
          />

          <div className="pa-uw-grid" data-testid="uw-grid-cd">
            <div className="pa-uw-grid__hint" data-testid="uw-grid-cd-hint" title="下方三个面板仅作记录与展示，后端持久化与跨项目同步暂未实现">
              下方三个面板仅作记录与展示，后端持久化与跨项目同步暂未实现。
            </div>
            <EvidenceSubmitPanel testId="uw-evidence" />
            <PaperLibraryEditor testId="uw-library" />
            <LocalRagAskPanel testId="uw-local-rag" />
          </div>
        </main>
      </div>
    </div>
  );
}