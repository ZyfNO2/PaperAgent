interface Revision {
  revision_id: string;
  parent_revision_id: string | null;
  revision_source: string;
  revision_reason?: string;
  nick_model_name?: string;
  narrative_summary?: string;
  diff?: { added?: Array<{field: string}>; removed?: Array<{field: string}>; changed?: Array<{field: string; old: string; new: string}> } | null;
}

const sourceLabels: Record<string, string> = {
  initial: '初始生成', devils_advocate: '反思审查', user_edit: '用户编辑', evidence_gap: '证据缺口',
};

export function NarrativeRevisions({ revisions }: { revisions: Revision[] }) {
  if (!revisions || revisions.length === 0) return null;
  return (
    <div>
      {revisions.map((rev) => (
        <div key={rev.revision_id} style={{ marginBottom: '16px', borderLeft: '3px solid #3b82f6', paddingLeft: '12px' }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
            <strong>{rev.revision_id}</strong>
            <span style={{ fontSize: '11px', padding: '2px 6px', borderRadius: '4px', background: '#eff6ff', color: '#3b82f6' }}>
              {sourceLabels[rev.revision_source] || rev.revision_source}
            </span>
            {rev.parent_revision_id && <span style={{ fontSize: '12px', color: '#94a3b8' }}>← {rev.parent_revision_id}</span>}
          </div>
          {rev.nick_model_name && <div style={{ fontWeight: 600, fontSize: '14px' }}>{rev.nick_model_name}</div>}
          {rev.narrative_summary && <p style={{ fontSize: '13px', color: '#64748b', margin: '4px 0' }}>{rev.narrative_summary.slice(0, 300)}{rev.narrative_summary.length > 300 ? '...' : ''}</p>}
          {rev.revision_reason && <p style={{ fontSize: '12px', color: '#f59e0b' }}>原因: {rev.revision_reason}</p>}
          {rev.diff && (rev.diff.changed?.length || rev.diff.added?.length || rev.diff.removed?.length) ? (
            <div style={{ fontSize: '12px', padding: '4px 8px', background: '#f8fafc', borderRadius: '4px' }}>
              {rev.diff.changed?.map((c, j) => <div key={`c${j}`}>变更: {c.field}</div>)}
              {rev.diff.added?.map((a, j) => <div key={`a${j}`} style={{ color: '#22c55e' }}>+ {a.field}</div>)}
              {rev.diff.removed?.map((r, j) => <div key={`r${j}`} style={{ color: '#ef4444' }}>- {r.field}</div>)}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
