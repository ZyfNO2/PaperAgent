import { useState, useEffect } from 'react';
import { LoadingDots } from './LoadingDots';

interface Answer {
  answer: string;
  confidence: number;
  cited_chunks: string[];
  retrieved_chunks: Array<{ chunk_id: string; score: number; text: string; source: string }>;
}

export function RagContextSection({ caseId }: { caseId: string }) {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hasIndex, setHasIndex] = useState<boolean | null>(null);

  useEffect(() => {
    fetch('/api/v1/acp/invoke', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ capability: 'get_knowledge_graph', params: { case_id: caseId } }),
    }).then(r => r.json()).then(data => {
      setHasIndex(data.success && data.result?.n_nodes > 0);
    }).catch(() => setHasIndex(false));
  }, [caseId]);

  const handleAsk = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch('/api/v1/acp/invoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capability: 'query_rag', params: { question, case_id: caseId } }),
      });
      const data = await resp.json();
      if (data.success) setAnswer(data.result);
      else setError(data.error?.message || '查询失败');
    } catch {
      setError('网络错误');
    }
    setLoading(false);
  };

  return (
    <details className="report-section">
      <summary>📚 RAG 问答</summary>
      <div className="report-content" style={{ padding: '12px' }}>
        {hasIndex === false && (
          <p style={{ fontSize: '14px', color: '#64748b' }}>
            尚未入库 PDF。请到 RAG 页面入库后再提问。
          </p>
        )}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
          <input
            type="text" placeholder="针对本 case 的论文提问..." value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
            style={{ flex: 1, padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: '8px' }}
            disabled={hasIndex === false}
          />
          <button className="btn-primary" onClick={handleAsk} disabled={loading || !question.trim()}>
            {loading ? <LoadingDots text="查询中" /> : '提问'}
          </button>
        </div>
        {answer && (
          <div style={{ padding: '12px', background: '#f8fafc', borderRadius: '8px' }}>
            <p>{answer.answer}</p>
            <div style={{ fontSize: '12px', color: '#64748b' }}>
              置信度: {(answer.confidence * 100).toFixed(0)}% · 引用: {answer.cited_chunks?.join(', ')}
            </div>
            {answer.retrieved_chunks && answer.retrieved_chunks.length > 0 && (
              <div style={{ marginTop: '8px' }}>
                {answer.retrieved_chunks.map((c, i) => (
                  <details key={i} style={{ marginBottom: '4px' }}>
                    <summary style={{ cursor: 'pointer', fontSize: '12px' }}>{c.chunk_id} (score={c.score})</summary>
                    <pre style={{ padding: '4px', background: '#fff', fontSize: '11px', whiteSpace: 'pre-wrap' }}>{c.text}</pre>
                  </details>
                ))}
              </div>
            )}
          </div>
        )}
        {error && <p style={{ color: '#ef4444', fontSize: '14px' }}>{error}</p>}
      </div>
    </details>
  );
}
