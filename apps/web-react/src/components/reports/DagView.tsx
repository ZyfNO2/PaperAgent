interface DagData {
  nodes: Array<{ id: string; title: string; effort?: string }>;
  edges: Array<{ from: string; to: string }>;
  milestones: Array<{ id: string; packages: string[]; label: string }>;
  has_cycle: boolean;
}

export function DagView({ dag }: { dag: DagData }) {
  if (!dag || !dag.milestones || dag.milestones.length === 0) {
    return <div style={{ fontSize: '14px', color: '#64748b' }}>暂无工作包依赖关系</div>;
  }
  return (
    <div>
      {dag.has_cycle && <div style={{ color: '#ef4444', marginBottom: '8px', fontWeight: 600 }}>⚠️ 检测到循环依赖</div>}
      {dag.milestones.map((ms) => (
        <div key={ms.id} style={{ marginBottom: '16px' }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: '#3b82f6', marginBottom: '4px' }}>{ms.label}</div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {ms.packages.map((pkgId) => {
              const node = dag.nodes.find((n) => n.id === pkgId);
              return (
                <div key={pkgId} style={{ padding: '6px 12px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '13px' }}>
                  {node?.title || pkgId}
                  {node?.effort && <span style={{ marginLeft: '8px', fontSize: '11px', color: '#94a3b8' }}>{node.effort}</span>}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
