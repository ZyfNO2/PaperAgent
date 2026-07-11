interface BindingData {
  valid: boolean;
  issues?: Array<{ type: string; message: string }>;
  needs_evidence_items?: string[];
  orphan_packages?: string[];
  stale_items?: string[];
}

export function BindingValidation({ data }: { data: BindingData }) {
  if (!data) return null;
  return (
    <div>
      <div style={{ fontWeight: 600, color: data.valid ? '#22c55e' : '#f59e0b', marginBottom: '8px' }}>
        {data.valid ? '✅ 证据链一致' : '⚠️ 证据链存在问题'}
      </div>
      {data.needs_evidence_items && data.needs_evidence_items.length > 0 && (
        <div style={{ marginBottom: '8px' }}>
          <strong>需补充证据:</strong>
          <ul>{data.needs_evidence_items.map((item, i) => <li key={i} style={{ color: '#f59e0b' }}>{item}</li>)}</ul>
        </div>
      )}
      {data.issues && data.issues.length > 0 && (
        <div>
          <strong>问题列表:</strong>
          <ul>{data.issues.map((issue, i) => <li key={i}>{issue.message}</li>)}</ul>
        </div>
      )}
      {data.orphan_packages && data.orphan_packages.length > 0 && (
        <div style={{ color: '#ef4444' }}>
          <strong>孤儿工作包:</strong> {data.orphan_packages.join(', ')}
        </div>
      )}
      {data.stale_items && data.stale_items.length > 0 && (
        <div style={{ color: '#f59e0b', marginTop: '4px' }}>
          <strong>过期项:</strong> {data.stale_items.join(', ')}
        </div>
      )}
    </div>
  );
}
