interface FeasibilityData {
  score: number;
  verdict?: string;
  reason?: string;
  degradation_paths?: string[];
  risks?: string[];
  strengths?: string[];
}

const verdictLabels: Record<string, string> = {
  feasible: '可行', risky: '有风险', not_recommended: '不推荐', recommended: '推荐',
};

export function FeasibilityReport({ data }: { data: FeasibilityData }) {
  if (!data) return null;
  const scoreColor = data.score >= 75 ? '#22c55e' : data.score >= 50 ? '#f59e0b' : '#ef4444';
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '12px' }}>
        <div style={{ fontSize: '32px', fontWeight: 700, color: scoreColor }}>{data.score}</div>
        <div>
          <div style={{ fontSize: '16px', fontWeight: 600 }}>
            {verdictLabels[data.verdict || ''] || data.verdict || '未知'}
          </div>
        </div>
      </div>
      {data.reason && <p style={{ marginBottom: '8px', fontSize: '14px' }}>{data.reason}</p>}
      {data.strengths && data.strengths.length > 0 && (
        <div style={{ marginBottom: '8px' }}>
          <h4>优势</h4>
          <ul>{data.strengths.map((p, i) => <li key={i}>{p}</li>)}</ul>
        </div>
      )}
      {data.degradation_paths && data.degradation_paths.length > 0 && (
        <div style={{ marginBottom: '8px' }}>
          <h4>降级路径</h4>
          <ul>{data.degradation_paths.map((p, i) => <li key={i}>{p}</li>)}</ul>
        </div>
      )}
      {data.risks && data.risks.length > 0 && (
        <div>
          <h4>风险</h4>
          <ul>{data.risks.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
