"""Re7.6 FeedbackBar React component.

Renders inline feedback controls on final recommendation, innovation card,
and RAG answer sections. Feedback is append-only; never enters LLM context.
"""
import { useState } from "react";

interface FeedbackBarProps {
  caseId: string;
  artifactType: "paper" | "report" | "innovation_card" | "rag_answer";
  artifactId: string;
  onFeedback?: () => void;
}

const VERDICTS = [
  { key: "useful", label: "有用" },
  { key: "incorrect", label: "有误" },
  { key: "unsupported", label: "无证据支持" },
  { key: "needs_more_evidence", label: "需要更多证据" },
];

export function FeedbackBar({ caseId, artifactType, artifactId, onFeedback }: FeedbackBarProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [sending, setSending] = useState(false);

  const handleSubmit = async () => {
    if (!selected) return;
    setSending(true);
    try {
      const idKey = `${caseId}-${artifactType}-${artifactId}-${Date.now()}`;
      const resp = await fetch("/api/v1/feedback/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: caseId,
          idempotency_key: idKey,
          artifact_type: artifactType,
          artifact_id: artifactId,
          verdict: selected,
          comment: comment.slice(0, 1000),
          client_version: "re7.6",
        }),
      });
      if (resp.ok) {
        setSubmitted(true);
        onFeedback?.();
      }
    } catch {
      // Silently fail — feedback is best-effort
    } finally {
      setSending(false);
    }
  };

  if (submitted) {
    return <span className="feedback-submitted">已提交反馈</span>;
  }

  return (
    <div className="feedback-bar">
      <span className="feedback-label">这篇内容有帮助吗？</span>
      <div className="feedback-buttons">
        {VERDICTS.map((v) => (
          <button
            key={v.key}
            className={`feedback-btn ${selected === v.key ? "active" : ""}`}
            onClick={() => setSelected(v.key)}
            disabled={sending}
          >
            {v.label}
          </button>
        ))}
      </div>
      {selected && (
        <div className="feedback-detail">
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value.slice(0, 1000))}
            placeholder="补充说明（可选，不超过1000字）"
            rows={2}
            maxLength={1000}
          />
          <button onClick={handleSubmit} disabled={sending}>
            {sending ? "提交中..." : "提交反馈"}
          </button>
        </div>
      )}
    </div>
  );
}
