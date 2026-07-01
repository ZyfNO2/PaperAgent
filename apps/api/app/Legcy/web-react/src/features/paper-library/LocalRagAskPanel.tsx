// Session 60: LocalRagAskPanel — 本地 RAG 问答 (M3 接线).
// ponytail:
// - 不调 RAG Eval; 不展示 recall/MRR/NDCG
// - 不强依赖 LLM; 服务端 LLM 不可用 / 无命中都明确显示
// - 不在 RAG 库为空时假装有答案

import { useState } from "react";
import { ApiError, apiClient } from "../../app/apiClient";

export interface LocalRagAskPanelProps {
  testId?: string;
  projectId?: string;
  apiPrefix?: string;
}

interface LocalEvidenceRef {
  paper_id: string;
  chunk_id: string;
  section_title: string | null;
  chunk_type: string | null;
  page_start: number | null;
  page_end: number | null;
  quote: string;
  score: number;
}

interface LocalAskResp {
  question: string;
  answer: string;
  evidence_refs: LocalEvidenceRef[];
  retrieval_mode: string;
  confidence: number;
  no_hit: boolean;
  message: string;
}

const DEFAULT_PROJECT = "demo-local-rag";

export function LocalRagAskPanel({
  testId,
  projectId = DEFAULT_PROJECT,
  apiPrefix = "/api/v1",
}: LocalRagAskPanelProps) {
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<LocalAskResp | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canAsk = question.trim().length > 0 && !busy;

  async function ask() {
    if (!canAsk) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const resp = await apiClient.post<LocalAskResp>(
        `${apiPrefix}/projects/${projectId}/paper-library/local-ask`,
        { question: question.trim(), top_k: 3 },
      );
      setResult(resp);
    } catch (e) {
      const msg = e instanceof ApiError ? `${e.status}: ${e.message}` : String(e);
      setError(`问答失败: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="pa-uw-zone" data-testid={testId ?? "local-rag-panel"}>
      <header className="pa-uw-zone__head">
        <span className="pa-uw-zone__cap">E</span>
        <h2 className="pa-uw-zone__title">本地 RAG 问答</h2>
        <div className="pa-uw-zone__meta">
          基于上方文献库的本地 embedding 索引, 不调用 LLM 也不接 Evidence Ledger
        </div>
      </header>
      <div className="pa-uw-zone__body">
        <div className="pa-uw-form">
          <label className="pa-uw-form__row">
            <span className="pa-uw-form__label">问题</span>
            <textarea
              className="pa-uw-form__textarea"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={2}
              placeholder="例: 这篇文献用了什么数据集？"
              data-testid="local-rag-question"
            />
          </label>
          <div className="pa-uw-form__actions">
            <button
              type="button"
              className="pa-btn pa-btn--primary pa-btn--md"
              onClick={ask}
              disabled={!canAsk}
              data-testid="local-rag-submit"
            >
              {busy ? "检索中..." : "提问"}
            </button>
          </div>
          {error && (
            <div className="pa-uw-form__error" data-testid="local-rag-error">
              {error}
            </div>
          )}
        </div>
        {result && (
          <div
            className={
              "pa-uw-rag-result pa-uw-rag-result--" + (result.no_hit ? "empty" : "hit")
            }
            data-testid="local-rag-result"
          >
            <div className="pa-uw-rag-result__head">
              <span data-testid="local-rag-mode">
                模式: {result.retrieval_mode}
              </span>
              <span data-testid="local-rag-conf">
                置信度: {result.confidence.toFixed(3)}
              </span>
              {result.no_hit && (
                <span
                  className="pa-uw-rag-result__badge pa-uw-rag-result__badge--empty"
                  data-testid="local-rag-no-hit"
                >
                  未命中
                </span>
              )}
            </div>
            <div
              className="pa-uw-rag-result__answer"
              data-testid="local-rag-answer"
            >
              {result.answer}
            </div>
            {result.evidence_refs.length > 0 && (
              <ul className="pa-uw-rag-result__refs" data-testid="local-rag-refs">
                {result.evidence_refs.map((r) => (
                  <li
                    key={r.chunk_id}
                    className="pa-uw-rag-result__ref"
                    data-testid={`local-rag-ref-${r.chunk_id}`}
                  >
                    <div className="pa-uw-rag-result__ref-head">
                      <code data-testid={`local-rag-ref-cid-${r.chunk_id}`}>
                        {r.chunk_id}
                      </code>
                      <span data-testid={`local-rag-ref-pid-${r.chunk_id}`}>
                        paper: {r.paper_id}
                      </span>
                      {r.section_title && (
                        <span>{r.section_title}</span>
                      )}
                      <span data-testid={`local-rag-ref-score-${r.chunk_id}`}>
                        score: {r.score.toFixed(3)}
                      </span>
                    </div>
                    <blockquote
                      className="pa-uw-rag-result__quote"
                      data-testid={`local-rag-ref-quote-${r.chunk_id}`}
                    >
                      {r.quote}
                    </blockquote>
                  </li>
                ))}
              </ul>
            )}
            {result.message && (
              <div className="pa-uw-rag-result__msg">{result.message}</div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}