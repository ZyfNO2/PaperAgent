interface InnovationPoint {
  description: string;
  baseline_used?: string;
  candidate_ids?: string[];
  novelty_score?: number;
  feasibility_score?: number;
  evidence_score?: number;
  status?: string;
}

export function InnovationReport({ data }: { data: { innovation_points?: InnovationPoint[] } }) {
  if (!data) return null;
  const points = data.innovation_points || [];
  return (
    <div>
      {points.map((ip, i) => (
        <div key={i} style={{ marginBottom: '12px', padding: '12px', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
            <strong>创新点 {i + 1}</strong>
            {ip.status === 'needs_evidence' && <span style={{ color: '#ef4444', fontSize: '12px' }}>⚠️ 缺证据</span>}
            {ip.status === 'stale' && <span style={{ color: '#f59e0b', fontSize: '12px' }}>⏰ 过期</span>}
          </div>
          <p style={{ fontSize: '14px', marginBottom: '4px' }}>{ip.description}</p>
          <div style={{ display: 'flex', gap: '12px', fontSize: '12px', color: '#64748b', flexWrap: 'wrap' }}>
            {ip.baseline_used && <span>Baseline: {ip.baseline_used}</span>}
            {ip.candidate_ids && ip.candidate_ids.length > 0 && <span>引用: {ip.candidate_ids.join(', ')}</span>}
          </div>
          {(ip.novelty_score !== undefined || ip.feasibility_score !== undefined || ip.evidence_score !== undefined) && (
            <div style={{ display: 'flex', gap: '12px', marginTop: '4px', flexWrap: 'wrap' }}>
              {ip.novelty_score !== undefined && <span style={{ fontSize: '12px' }}>新颖性: {ip.novelty_score}/10</span>}
              {ip.feasibility_score !== undefined && <span style={{ fontSize: '12px' }}>可行性: {ip.feasibility_score}/10</span>}
              {ip.evidence_score !== undefined && <span style={{ fontSize: '12px' }}>证据强度: {ip.evidence_score}/10</span>}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
