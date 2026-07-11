interface DimensionScore { dimension: string; score: number; verdict: string; reason: string; }
interface EvidenceCritique {
  target_type: string; target_id: string; issue: string;
  severity: string; suggested_fix?: string;
}
interface ReviewData {
  overall_verdict?: string;
  dimension_scores?: DimensionScore[];
  fabrication_alerts?: string[];
  risks_identified?: string[];
  evidence_critiques?: EvidenceCritique[];
}

const VERDICT_LABELS: Record<string, { label: string; color: string }> = {
  ACCEPT: { label: '通过', color: '#22c55e' },
  MINOR_REVISION: { label: '小修', color: '#f59e0b' },
  BLOCK: { label: '阻断', color: '#ef4444' },
};

const SEVERITY_STYLES: Record<string, { bg: string; color: string }> = {
  critical: { bg: '#fef2f2', color: '#ef4444' },
  major: { bg: '#fefce8', color: '#f59e0b' },
  minor: { bg: '#f0fdf4', color: '#22c55e' },
};

export function ReviewReport({ data }: { data: ReviewData }) {
  if (!data) return null;
  const v = VERDICT_LABELS[data.overall_verdict || ''] || { label: data.overall_verdict, color: '#64748b' };
  return (
    <div>
      <div style={{ fontSize: '18px', fontWeight: 700, color: v.color, marginBottom: '12px' }}>{v.label}</div>
      {data.dimension_scores?.map((d, i) => {
        const sc = d.score >= 6 ? '#22c55e' : d.score >= 4 ? '#f59e0b' : '#ef4444';
        return (
          <div key={i} style={{ marginBottom: '8px', padding: '8px', background: '#f8fafc', borderRadius: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <strong>{d.dimension}</strong>
              <span style={{ color: sc }}>{d.score}/10</span>
            </div>
            <p style={{ fontSize: '13px', color: '#64748b', margin: '4px 0 0 0' }}>{d.reason}</p>
          </div>
        );
      })}
      {data.fabrication_alerts && data.fabrication_alerts.length > 0 && (
        <div style={{ padding: '8px', background: '#fef2f2', borderRadius: '6px', marginBottom: '8px' }}>
          <strong>⚠️ 编造警告</strong>
          <ul>{data.fabrication_alerts.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </div>
      )}
      {data.evidence_critiques && data.evidence_critiques.length > 0 && (
        <div>
          <h4>证据级审查意见</h4>
          {data.evidence_critiques.map((c, i) => {
            const sv = SEVERITY_STYLES[c.severity] || SEVERITY_STYLES.minor;
            return (
              <div key={i} style={{ marginBottom: '8px', padding: '8px', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <span style={{ fontSize: '11px', padding: '2px 6px', borderRadius: '4px', background: sv.bg, color: sv.color }}>{c.severity}</span>
                  <span style={{ fontSize: '12px', fontFamily: 'monospace' }}>{c.target_type}: {c.target_id}</span>
                </div>
                <p style={{ fontSize: '13px', marginTop: '4px' }}>{c.issue}</p>
                {c.suggested_fix && <p style={{ fontSize: '12px', color: '#3b82f6' }}>💡 {c.suggested_fix}</p>}
              </div>
            );
          })}
        </div>
      )}
      {data.risks_identified && data.risks_identified.length > 0 && (
        <div><h4>风险</h4><ul>{data.risks_identified.map((r, i) => <li key={i}>{r}</li>)}</ul></div>
      )}
    </div>
  );
}
