import { useState } from 'react';
import { LoadingDots } from '../components/LoadingDots';
import { ErrorState } from '../components/ErrorState';

interface IngestResult {
  status?: string;
  n_chunks?: number;
  n_terms?: number;
  reason?: string;
}

interface RetrievedChunk {
  chunk_id: string;
  score: number;
  text: string;
  source: string;
}

interface Answer {
  answer: string;
  confidence: number;
  cited_chunks: string[];
  retrieved_chunks: RetrievedChunk[];
  case_id: string;
}

export function RagPlaceholder() {
  const [pdfUrl, setPdfUrl] = useState('');
  const [caseId, setCaseId] = useState('');
  const [question, setQuestion] = useState('');
  const [ingesting, setIngesting] = useState(false);
  const [asking, setAsking] = useState(false);
  const [ingestResult, setIngestResult] = useState<IngestResult | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleIngest = async () => {
    if (!pdfUrl.trim()) return;
    setIngesting(true);
    setError(null);
    try {
      const resp = await fetch('/api/v1/acp/invoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-ACP-Capability': 'write' },
        body: JSON.stringify({
          capability: 'ingest_pdf',
          params: { pdf_url: pdfUrl, case_id: caseId || 'global' },
        }),
      });
      const data = await resp.json();
      if (data.success) {
        setIngestResult(data.result);
      } else {
        setError(data.error?.message || '入库失败');
      }
    } catch (e) {
      setError('网络错误：' + (e instanceof Error ? e.message : 'unknown'));
    }
    setIngesting(false);
  };

  const handleAsk = async () => {
    if (!question.trim()) return;
    setAsking(true);
    setError(null);
    try {
      const resp = await fetch('/api/v1/acp/invoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          capability: 'query_rag',
          params: { question, case_id: caseId || 'global' },
        }),
      });
      const data = await resp.json();
      if (data.success) {
        setAnswer(data.result);
      } else {
        setError(data.error?.message || '查询失败');
      }
    } catch (e) {
      setError('网络错误：' + (e instanceof Error ? e.message : 'unknown'));
    }
    setAsking(false);
  };

  return (
    <div>
      <h2 style={{ marginBottom: '24px' }}>📚 RAG 问答</h2>

      {/* Step 1: Ingest PDF */}
      <div style={{ marginBottom: '24px' }}>
        <h3>步骤 1：入库 PDF</h3>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
          <input
            type="text"
            placeholder="PDF URL (如 https://arxiv.org/pdf/2401.00001)"
            value={pdfUrl}
            onChange={(e) => setPdfUrl(e.target.value)}
            style={{ flex: 1, padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: '8px' }}
          />
          <input
            type="text"
            placeholder="Case ID (可选)"
            value={caseId}
            onChange={(e) => setCaseId(e.target.value)}
            style={{ width: '150px', padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: '8px' }}
          />
          <button
            className="btn-primary"
            onClick={handleIngest}
            disabled={ingesting || !pdfUrl.trim()}
          >
            {ingesting ? <LoadingDots text="入库中" /> : '入库'}
          </button>
        </div>
        {ingestResult && (
          <div style={{ padding: '8px 16px', background: '#f0fdf4', borderRadius: '8px', fontSize: '14px' }}>
            {ingestResult.status === 'ok' ? (
              <>✅ 入库成功：{ingestResult.n_chunks || 0} 个文本块，{ingestResult.n_terms || 0} 个词项</>
            ) : (
              <>❌ 入库失败：{ingestResult.reason || '未知原因'}</>
            )}
          </div>
        )}
      </div>

      {/* Step 2: Ask question */}
      <div style={{ marginBottom: '24px' }}>
        <h3>步骤 2：提问</h3>
        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            type="text"
            placeholder="输入问题..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
            style={{ flex: 1, padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: '8px' }}
            disabled={!ingestResult || ingestResult.status !== 'ok'}
          />
          <button
            className="btn-primary"
            onClick={handleAsk}
            disabled={asking || !question.trim() || !ingestResult || ingestResult.status !== 'ok'}
          >
            {asking ? <LoadingDots text="查询中" /> : '提问'}
          </button>
        </div>
      </div>

      {/* Answer */}
      {answer && (
        <div style={{ marginBottom: '24px' }}>
          <h3>回答</h3>
          <div style={{ padding: '16px', background: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
            <p style={{ marginBottom: '12px' }}>{answer.answer}</p>
            <div style={{ fontSize: '13px', color: '#64748b' }}>
              置信度：{(answer.confidence * 100).toFixed(0)}% ·
              引用：{answer.cited_chunks.join(', ')}
            </div>
          </div>

          {answer.retrieved_chunks && answer.retrieved_chunks.length > 0 && (
            <div style={{ marginTop: '16px' }}>
              <h4>检索到的片段</h4>
              {answer.retrieved_chunks.map((c, i) => (
                <details key={i} style={{ marginBottom: '8px' }}>
                  <summary style={{ cursor: 'pointer', fontSize: '13px' }}>
                    {c.chunk_id} (score={c.score})
                  </summary>
                  <pre style={{ padding: '8px', background: '#f8fafc', fontSize: '12px', whiteSpace: 'pre-wrap' }}>
                    {c.text}
                  </pre>
                </details>
              ))}
            </div>
          )}
        </div>
      )}

      {error && <ErrorState title="操作失败" message={error} onRetry={() => setError(null)} />}
    </div>
  );
}
