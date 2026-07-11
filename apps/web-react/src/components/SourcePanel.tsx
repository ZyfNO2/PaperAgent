interface SourceEntry {
  name: string;
  status: string;
  count: number;
}

const STATUS_ICONS: Record<string, string> = {
  ok: '✅',
  empty: '⚠️',
  error: '❌',
  rate_limited: '⚠️',
  skipped: '⏭️',
};

const STATUS_LABELS: Record<string, string> = {
  ok: '',
  empty: '无结果',
  error: '失败',
  rate_limited: '限流',
  skipped: '已跳过',
};

const SOURCE_NAMES: Record<string, string> = {
  arxiv: 'arXiv',
  crossref: 'Crossref',
  github: 'GitHub',
  openalex: 'OpenAlex',
  semantic_scholar: 'Semantic Scholar',
  huggingface: 'HuggingFace',
  core: 'CORE',
};

export function SourcePanel({ sources }: { sources: SourceEntry[] }) {
  if (sources.length === 0) return null;
  return (
    <div className="source-panel">
      <h3>来源状态</h3>
      <div className="source-grid">
        {sources.map((s) => (
          <div key={s.name} className="source-item">
            <span className="source-status-icon">{STATUS_ICONS[s.status] || '❓'}</span>
            <span className="source-name">{SOURCE_NAMES[s.name] || s.name}</span>
            <span className="source-count">
              {s.status === 'skipped' ? STATUS_LABELS.skipped :
               s.status === 'ok' ? `${s.count} 篇` :
               STATUS_LABELS[s.status] || `${s.count}`}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
