import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { submitTopic, listCases } from '../lib/api';
import { EmptyState } from '../components/EmptyState';
import { LoadingDots } from '../components/LoadingDots';

const DEMO_CASES = [
  {
    title: '基于YOLO的钢材表面缺陷检测',
    description: '工业视觉质检场景，有公开数据集和 baseline',
    label: '工科 · 计算机视觉',
  },
  {
    title: '基于大语言模型的医学问答可信度评估方法研究',
    description: '医学AI合规场景，涉及安全性和可信度',
    label: '医学 · AI安全',
  },
];

interface CaseItem {
  case_id: string;
  status: string;
  mtime: number;
  topic?: string;
  score?: number;
}

interface ProviderInfo {
  name: string;
  model: string;
  label: string;
  enabled: boolean;
}

export function Home() {
  const navigate = useNavigate();
  const [topic, setTopic] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<CaseItem[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [activeProvider, setActiveProvider] = useState('');
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    listCases()
      .then(async (data) => {
        const cases = (data.cases || []).slice(0, 10);
        const enriched = await Promise.all(
          cases.map(async (c: CaseItem) => {
            try {
              const resp = await fetch(`/api/v1/research/${c.case_id}/state`);
              if (resp.ok) {
                const state = await resp.json();
                return {
                  ...c,
                  topic: state.topic as string,
                  score: state.feasibility_report?.score as number | undefined,
                };
              }
            } catch { /* ignore */ }
            return c;
          })
        );
        setHistory(enriched);
      })
      .catch(() => {});

    // Load providers
    fetch('/api/v1/llm/providers')
      .then(r => r.json())
      .then(data => {
        setProviders(data.providers || []);
        setActiveProvider(data.active_primary || '');
      })
      .catch(() => {});
  }, []);

  const handleSubmit = async (topicText?: string) => {
    const t = (topicText || topic).trim();
    if (!t) return;
    setLoading(true);
    setError(null);
    try {
      const result = await submitTopic(t);
      navigate(`/workbench/${result.case_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败');
      setLoading(false);
    }
  };

  const loadHistory = (caseId: string) => {
    navigate(`/workbench/${caseId}`);
  };

  const switchProvider = async (name: string) => {
    if (name === activeProvider) return;
    setSwitching(true);
    try {
      const resp = await fetch('/api/v1/llm/active', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-ACP-Capability': 'write' },
        body: JSON.stringify({ primary: name }),
      });
      const data = await resp.json();
      if (data.success) {
        setActiveProvider(name);
      }
    } catch { /* ignore */ }
    setSwitching(false);
  };

  return (
    <div>
      <div className="home-hero">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
          <div>
            <h1>PaperAgent</h1>
            <div className="subtitle">题目研究智能工作台</div>
          </div>
          {providers.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
              <span style={{ color: 'var(--color-text-secondary)' }}>🤖</span>
              <select
                value={activeProvider}
                onChange={(e) => switchProvider(e.target.value)}
                disabled={switching}
                style={{
                  padding: '4px 8px', borderRadius: '6px', border: '1px solid #e2e8f0',
                  background: '#fff', fontSize: '13px', cursor: 'pointer',
                }}
              >
                {providers.map(p => (
                  <option key={p.name} value={p.name}>
                    {p.label} ({p.model})
                  </option>
                ))}
              </select>
              {switching && <LoadingDots text="" />}
            </div>
          )}
        </div>

        <div className="description">
          输入一个题目，获得完整的证据链和可行性分析报告
        </div>

        <div className="home-steps">
          <div className="home-step">
            <div className="step-number">1️⃣</div>
            <div className="step-title">输入题目</div>
            <div className="step-desc">AI 自动分解关键词</div>
          </div>
          <div className="home-step">
            <div className="step-number">2️⃣</div>
            <div className="step-title">智能检索</div>
            <div className="step-desc">多源验证论文质量</div>
          </div>
          <div className="home-step">
            <div className="step-number">3️⃣</div>
            <div className="step-title">审核报告</div>
            <div className="step-desc">导出可行性报告</div>
          </div>
        </div>

        <div className="home-input-row">
          <input
            type="text"
            placeholder="🔍 输入题目..."
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            disabled={loading}
            aria-label="研究题目输入"
          />
          <button
            className="btn-primary"
            onClick={() => handleSubmit()}
            disabled={loading || !topic.trim()}
          >
            {loading ? <LoadingDots text="提交中" /> : '开始研究'}
          </button>
        </div>

        {error && (
          <div style={{ color: 'var(--color-error)', fontSize: '14px', marginBottom: '16px' }}>
            {error}
          </div>
        )}

        <div className="home-demos">
          {DEMO_CASES.map((demo) => (
            <div
              key={demo.title}
              className="demo-card"
              onClick={() => handleSubmit(demo.title)}
            >
              <div className="demo-label">{demo.label}</div>
              <div className="demo-title">{demo.title}</div>
              <div className="demo-desc">{demo.description}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="home-history">
        <h3>最近研究</h3>
        {history.length === 0 ? (
          <EmptyState
            icon="📂"
            title="还没有研究记录"
            description="输入题目开始第一次研究"
          />
        ) : (
          <div className="history-list">
            {history.map((item) => (
              <div
                key={item.case_id}
                className="history-item"
                onClick={() => loadHistory(item.case_id)}
              >
                <div>
                  <span className="case-id">{item.case_id}</span>
                  {item.topic && (
                    <div style={{ fontSize: '13px', color: 'var(--color-text)', marginTop: '2px' }}>
                      {item.topic.length > 50 ? item.topic.slice(0, 50) + '...' : item.topic}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {item.score !== undefined && (
                    <span style={{
                      fontSize: '12px', fontWeight: 600,
                      color: item.score >= 75 ? '#22c55e' : item.score >= 50 ? '#f59e0b' : '#ef4444',
                    }}>
                      {item.score}
                    </span>
                  )}
                  <span className={`case-status ${item.status}`}>{item.status}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
