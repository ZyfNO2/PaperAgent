// Session 59: UserWorkbenchPage — 极简主工作台
// 4 区合一: A 题目输入 + B AI 交互 + C 证据提交 + D 文献 RAG 库编辑.
// 普通模式首屏直达, 不再点 "进入工作台".
// 高级内容 (RAG Eval 指标 / ThesisEval / Interview Tech Switches / Trace / Old frontend)
// 全部迁入 DeveloperPanel 抽屉 (开发者窗口).
import { useState } from "react";
import { TopicIntake } from "../step-workbench/components/TopicIntake";
import { WorkbenchChat } from "../step-workbench/components/WorkbenchChat";
import { EvidenceSubmitPanel } from "../evidence/EvidenceSubmitPanel";
import { PaperLibraryEditor } from "../paper-library/PaperLibraryEditor";
import type { ChatMessage } from "../step-workbench/stepTypes";
import type { CommandPreview } from "../step-workbench/stepWorkbenchReducer";

const QUICK_ACTIONS = [
  { key: "modify", label: "修改题目", text: "请把题目改为: " },
  { key: "constraint", label: "补充约束", text: "补充约束: " },
  { key: "retrieve", label: "让 AI 查证据", text: "请帮我查证: " },
  { key: "next", label: "生成下一步建议", text: "请给我下一步建议" },
] as const;

const NOTES_KEY = "paperagent:notes";

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

export interface UserWorkbenchPageProps {
  testId?: string;
}

export function UserWorkbenchPage({ testId }: UserWorkbenchPageProps) {
  const [topicInput, setTopicInput] = useState("");
  const [topic, setTopic] = useState("");
  const [status, setStatus] = useState<"尚未开始" | "正在理解题目" | "等待确认" | "已确认">(
    "尚未开始",
  );
  const [notes, setNotes] = useState<string[]>(() => loadNotes());

  const [chatDraft, setChatDraft] = useState("");
  const [chatPreview, setChatPreview] = useState<CommandPreview | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  function pushMsg(role: "assistant" | "system", text: string) {
    setMessages((prev) => [
      ...prev,
      {
        id: `${role === "assistant" ? "a" : "s"}-${Date.now()}-${Math.random()
          .toString(36)
          .slice(2, 6)}`,
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

  function onStart() {
    const t = topicInput.trim();
    if (!t) return;
    setTopic(t);
    setStatus("正在理解题目");
    // 简易 heuristic: 不引 LLM, 直接给一段低密度自然语言回复
    const words = pickKeywords(t);
    const reply =
      words.length > 0
        ? `我把题目拆成 ${words.length} 个关键词: ${words.join(" / ")}。\n下一步我会先找可复现论文和公开数据集。`
        : `题目收到。下一步我会先拆关键词, 再查可复现论文和公开数据集。`;
    pushAssistant(reply);
    setStatus("等待确认");
  }

  function pickKeywords(t: string): string[] {
    // ponytail: demo 占位, 不接 LLM
    const tokens = t
      .split(/[基于的在上,，。;；\s/]+/)
      .map((s) => s.trim())
      .filter((s) => s.length >= 2 && s.length <= 12);
    return tokens.slice(0, 4);
  }

  function submitChat(text: string) {
    const t = text.trim();
    if (!t) return;
    pushMsg("user", t);
    setChatDraft("");
    // intent detection: 修改 / 补充 / 让 AI 查 / 下一步
    if (/^(修改|改成|改为|更新)/.test(t)) {
      setChatPreview({
        kind: "set_topic",
        intent: "修改题目",
        description: t.replace(/^(修改|改成|改为|更新)\s*/, ""),
      });
    } else if (/^(补充|加上|添加约束)/.test(t)) {
      setChatPreview({
        kind: "add_note",
        intent: "补充约束",
        description: t.replace(/^(补充|加上|添加约束)\s*/, ""),
        payload: t.replace(/^(补充|加上|添加约束)\s*/, ""),
      });
    } else if (/^(让 AI 查|请查|检索|查询)/.test(t)) {
      const query = t.replace(/^(让 AI 查|请查|检索|查询)\s*/, "");
      setChatPreview({
        kind: "unsupported",
        intent: "查询证据",
        description: `暂未接入真实检索 (本地演示): ${query}`,
      });
    } else if (/下一步建议|下一步|建议/.test(t)) {
      pushAssistant(
        "建议接下来 1) 在文献库中收录 2-3 篇核心论文 2) 标注数据来源 3) 检查可行性约束。",
      );
      setChatPreview(null);
    } else {
      setChatPreview({
        kind: "unsupported",
        intent: "未识别指令",
        description: `演示模式暂不支持: ${t}`,
      });
    }
  }

  function applyPreview() {
    if (!chatPreview) return;
    if (chatPreview.kind === "set_topic") {
      setTopic(chatPreview.description);
      setTopicInput(chatPreview.description);
      pushSystem(`题目已更新为: ${chatPreview.description}`);
      setStatus("等待确认");
    } else if (chatPreview.kind === "add_note") {
      const note = chatPreview.payload ?? chatPreview.description;
      const next = [...notes, note];
      setNotes(next);
      saveNotes(next);
      pushSystem(`已添加约束: ${note}`);
    } else {
      pushSystem(`暂不支持的操作: ${chatPreview.intent}`);
    }
    setChatPreview(null);
  }

  return (
    <div className="pa-uw" data-testid={testId ?? "user-workbench"}>
      <header className="pa-uw-header" data-testid="uw-header">
        <h1 className="pa-uw-title">选题与开题工作台</h1>
        <p className="pa-uw-sub">
          输入题目, 与 AI 讨论, 提交证据, 维护文献库。
        </p>
      </header>

      {/* A. 题目输入 */}
      <section className="pa-uw-zone pa-uw-zone--a" data-testid="uw-zone-a">
        <header className="pa-uw-zone__head">
          <span className="pa-uw-zone__cap">A</span>
          <h2 className="pa-uw-zone__title">题目输入</h2>
          <span
            className={
              "pa-uw-zone__status pa-uw-zone__status--" +
              (status === "已确认"
                ? "ok"
                : status === "尚未开始"
                  ? "neutral"
                  : "info")
            }
            data-testid="uw-topic-status"
          >
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
        </div>
      </section>

      {/* B. 与 AI 的交互 */}
      <section className="pa-uw-zone pa-uw-zone--b" data-testid="uw-zone-b">
        <header className="pa-uw-zone__head">
          <span className="pa-uw-zone__cap">B</span>
          <h2 className="pa-uw-zone__title">与 AI 的交互</h2>
        </header>
        <div className="pa-uw-zone__body pa-uw-zone__body--b">
          <div className="pa-uw-quick">
            {QUICK_ACTIONS.map((q) => (
              <button
                key={q.key}
                type="button"
                className="pa-btn pa-btn--secondary pa-btn--sm"
                onClick={() => setChatDraft(q.text)}
                data-testid={`uw-quick-${q.key}`}
              >
                {q.label}
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

      {/* C + D: 双列 */}
      <div className="pa-uw-grid" data-testid="uw-grid-cd">
        <EvidenceSubmitPanel testId="uw-evidence" />
        <PaperLibraryEditor testId="uw-library" />
      </div>
    </div>
  );
}