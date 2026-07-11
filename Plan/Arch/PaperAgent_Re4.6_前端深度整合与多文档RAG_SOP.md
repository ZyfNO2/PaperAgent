# PaperAgent Re4.6：前端深度整合与多文档 RAG SOP

> **承接**：Re4.5 全文入库与 RAG 检索已完成（527 tests，ACP ingest_pdf/query_rag/get_knowledge_graph 全部接通，端到端 case re45-test 20 chunks 15 nodes）。
>
> **本 SOP 覆盖 Day 6 全部任务**：Workbench 深度整合（binding validation、narrative revisions、DAG、RAG 上下文）、多文档 RAG（merge index）、首页历史 Case 卡片增强、Playwright 回归。
>
> **预计时长**：6–8 小时，分 7 个 Phase。
> **模型**：DeepSeek v4 flash（via OpenCode proxy，`https://opencode.ai/go`）。
> **参考项目复用**：无新复用。基于 Re4.1–4.5 已有资产。

---

## 0. 当前事实基线（已验证）

### 后端已实现但前端尚未消费的数据

| 数据源 | 后端位置 | 前端当前状态 |
|---|---|---|
| `binding_validation` | `low_bar_review.binding_validation` (Re4.3) | ❌ 未展示 |
| `narrative_revisions` | `state.narrative_revisions` (Re4.3) | ❌ 未展示 |
| `dag` (work package DAG) | `/work-packages` API + `low_bar_review.dag` (Re4.3) | ❌ 未展示 |
| `evidence_critiques` | `review_report.evidence_critiques` (Re4.3) | ❌ 未展示 |
| `candidate_ids` on innovation | `innovation_points[].candidate_ids` (Re4.3) | ❌ 未展示 |
| RAG answer | ACP `query_rag` (Re4.5) | ❌ 仅在 /rag 页面，未整合到 Workbench |
| Knowledge graph from RAG | ACP `get_knowledge_graph` (Re4.5) | ❌ 未展示 |
| ACP ledger | `acp_ledger.jsonl` (Re4.4) | ❌ 未展示 |

### 前端现状

| 页面 | 组件 | 已有功能 | 缺失 |
|---|---|---|---|
| 首页 `/#/` | `Home.tsx` | 题目输入、Demo Case、历史列表 | 历史列表只显示 case_id + status，无摘要 |
| 工作台 `/#/workbench/:caseId` | `Workbench.tsx` | SSE 进度、论文列表、来源面板、9 个报告折叠区（raw JSON `<pre>`） | 报告区是原始 JSON dump，无可读性；无 binding/DAG/revision 展示 |
| RAG `/#/rag` | `RagPlaceholder.tsx` | PDF 入库 + 问答 + 引用展示 | 独立页面，未与 Workbench case 关联；不支持多 PDF |

### 现有 Workbench 报告渲染方式

```tsx
// 当前：原始 JSON dump
<details>
  <summary>{section.icon} {section.title}</summary>
  <div className="report-content">
    <pre>{JSON.stringify(data, null, 2)}</pre>
  </div>
</details>
```

Day 6 将替换为结构化渲染组件。

### 现有 RAG index 结构

```json
{
  "case_id": "xxx",
  "documents": [{"chunk_id": "chunk-0", "text": "...", "source": "url1"}],
  "vocabulary": {"term": df},
  "tfidf_vectors": [{"chunk_id": "chunk-0", "terms": {}}],
  "n_chunks": 20,
  "source": "url1"  // ← 单源
}
```

Day 6 将支持多源合并。

### 决策

- **报告渲染**：为每个 section 类型编写专用 React 组件（非通用 JSON dump）
- **多文档 RAG**：`build_index` 追加 `merge_index` 函数，合并多源 chunks + 重建 TF-IDF
- **RAG 整合**：Workbench 完成后追加"RAG 问答"折叠区，关联当前 case_id
- **历史卡片**：首页历史列表追加 topic 摘要 + feasibility score
- **不做**：不实现 embedding 升级（Day 7）；不修改后端 API；不修改 graph 拓扑

---

## 1. 本轮目标

### 核心交付

1. **结构化报告组件**：feasibility / review / innovation / narrative / work_packages / DAG 各有专用渲染
2. **Binding validation 展示**：展示验证结果 + needs_evidence 标记
3. **Narrative revisions 时间线**：展示修订历史 + diff
4. **DAG 可视化**：里程碑分层 + 依赖箭头
5. **多文档 RAG**：`merge_index` 函数 + ACP `ingest_pdf` 支持追加
6. **Workbench RAG 上下文**：完成后可对当前 case 的已入库 PDF 问答
7. **首页增强**：历史 case 卡片显示 topic + score + verdict
8. **Playwright 回归**：截图 + 功能验证

### 验收标准

- 报告区不再是 `<pre>` JSON dump，每个 section 有结构化 UI
- binding_validation 的 issues 和 needs_evidence 可见
- narrative_revisions 的 revision_id → diff 时间线可见
- DAG 的 milestones 分层可见
- 多 PDF 入库后 `query_rag` 可检索到全部文档的 chunks
- 首页历史卡片显示 topic 摘要
- Playwright 截图生成，全部测试 PASS

### 不做

- 不修改后端 API 或 graph 拓扑
- 不实现 embedding 向量检索（Day 7）
- 不实现 SQLite 持久化迁移（Day 7）
- 不实现完整论文编辑器
- 不做复杂动画

> **强制规则**：每个 Phase 完成后必须跑 `pytest --collect-only` 确认零 error；
> 全部 Phase 完成后必须跑一个端到端 case 验证产物完整性和正确性（见 Phase 7）。

---

## 2. Phase 设计

### Phase 1：结构化报告组件 — 2h

#### Fix 1.1: Feasibility 报告组件

**文件**：`apps/web-react/src/components/reports/FeasibilityReport.tsx`（新建）

```tsx
interface FeasibilityData {
  score: number;
  verdict?: string;
  reason?: string;
  degradation_paths?: string[];
  risks?: string[];
}

export function FeasibilityReport({ data }: { data: FeasibilityData }) {
  const scoreColor = data.score >= 75 ? '#22c55e' : data.score >= 50 ? '#f59e0b' : '#ef4444';
  const verdictLabel: Record<string, string> = {
    feasible: '可行', risky: '有风险', not_recommended: '不推荐',
  };
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '12px' }}>
        <div style={{ fontSize: '32px', fontWeight: 700, color: scoreColor }}>{data.score}</div>
        <div>
          <div style={{ fontSize: '16px', fontWeight: 600 }}>
            {verdictLabel[data.verdict || ''] || data.verdict || '未知'}
          </div>
        </div>
      </div>
      {data.reason && <p style={{ marginBottom: '8px', fontSize: '14px' }}>{data.reason}</p>}
      {data.degradation_paths && data.degradation_paths.length > 0 && (
        <div>
          <h4>降级路径</h4>
          <ul>{data.degradation_paths.map((p, i) => <li key={i}>{p}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
```

#### Fix 1.2: Review 报告组件

**文件**：`apps/web-react/src/components/reports/ReviewReport.tsx`（新建）

```tsx
interface DimensionScore { dimension: string; score: number; verdict: string; reason: string; }
interface ReviewData {
  overall_verdict?: string;
  dimension_scores?: DimensionScore[];
  fabrication_alerts?: string[];
  risks_identified?: string[];
  evidence_critiques?: Array<{ target_type: string; target_id: string; issue: string; severity: string; suggested_fix: string; }>;
}

const VERDICT_LABELS: Record<string, { label: string; color: string }> = {
  ACCEPT: { label: '通过', color: '#22c55e' },
  MINOR_REVISION: { label: '小修', color: '#f59e0b' },
  BLOCK: { label: '阻断', color: '#ef4444' },
};

export function ReviewReport({ data }: { data: ReviewData }) {
  const v = VERDICT_LABELS[data.overall_verdict || ''] || { label: data.overall_verdict, color: '#64748b' };
  return (
    <div>
      <div style={{ fontSize: '18px', fontWeight: 700, color: v.color, marginBottom: '12px' }}>{v.label}</div>
      {data.dimension_scores?.map((d, i) => (
        <div key={i} style={{ marginBottom: '8px', padding: '8px', background: '#f8fafc', borderRadius: '6px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <strong>{d.dimension}</strong>
            <span style={{ color: d.score >= 6 ? '#22c55e' : d.score >= 4 ? '#f59e0b' : '#ef4444' }}>{d.score}/10</span>
          </div>
          <p style={{ fontSize: '13px', color: '#64748b' }}>{d.reason}</p>
        </div>
      ))}
      {data.fabrication_alerts && data.fabrication_alerts.length > 0 && (
        <div style={{ padding: '8px', background: '#fef2f2', borderRadius: '6px', marginBottom: '8px' }}>
          <strong>⚠️ 编造警告</strong>
          <ul>{data.fabrication_alerts.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </div>
      )}
      {data.evidence_critiques && data.evidence_critiques.length > 0 && (
        <div>
          <h4>证据级审查意见</h4>
          {data.evidence_critiques.map((c, i) => (
            <div key={i} style={{ marginBottom: '8px', padding: '8px', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', padding: '2px 6px', borderRadius: '4px', background: c.severity === 'critical' ? '#fef2f2' : c.severity === 'major' ? '#fefce8' : '#f0fdf4', color: c.severity === 'critical' ? '#ef4444' : c.severity === 'major' ? '#f59e0b' : '#22c55e' }}>{c.severity}</span>
                <span style={{ fontSize: '12px', fontFamily: 'monospace' }}>{c.target_type}: {c.target_id}</span>
              </div>
              <p style={{ fontSize: '13px', marginTop: '4px' }}>{c.issue}</p>
              <p style={{ fontSize: '12px', color: '#3b82f6' }}>💡 {c.suggested_fix}</p>
            </div>
          ))}
        </div>
      )}
      {data.risks_identified && data.risks_identified.length > 0 && (
        <div><h4>风险</h4><ul>{data.risks_identified.map((r, i) => <li key={i}>{r}</li>)}</ul></div>
      )}
    </div>
  );
}
```

#### Fix 1.3: Innovation 报告组件

**文件**：`apps/web-react/src/components/reports/InnovationReport.tsx`（新建）

```tsx
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
  const points = data.innovation_points || [];
  return (
    <div>
      {points.map((ip, i) => (
        <div key={i} style={{ marginBottom: '12px', padding: '12px', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
            <strong>创新点 {i + 1}</strong>
            {ip.status === 'needs_evidence' && <span style={{ color: '#ef4444', fontSize: '12px' }}>⚠️ 缺证据</span>}
          </div>
          <p style={{ fontSize: '14px', marginBottom: '4px' }}>{ip.description}</p>
          <div style={{ display: 'flex', gap: '12px', fontSize: '12px', color: '#64748b' }}>
            {ip.baseline_used && <span>Baseline: {ip.baseline_used}</span>}
            {ip.candidate_ids && ip.candidate_ids.length > 0 && <span>引用: {ip.candidate_ids.join(', ')}</span>}
          </div>
          {(ip.novelty_score !== undefined || ip.feasibility_score !== undefined || ip.evidence_score !== undefined) && (
            <div style={{ display: 'flex', gap: '12px', marginTop: '4px' }}>
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
```

#### Fix 1.4: Narrative Revisions 时间线组件

**文件**：`apps/web-react/src/components/reports/NarrativeRevisions.tsx`（新建）

```tsx
interface Revision {
  revision_id: string;
  parent_revision_id: string | null;
  revision_source: string;
  revision_reason?: string;
  nick_model_name?: string;
  narrative_summary?: string;
  diff?: { added?: any[]; removed?: any[]; changed?: any[] } | null;
}

export function NarrativeRevisions({ revisions }: { revisions: Revision[] }) {
  if (!revisions || revisions.length === 0) return null;
  const sourceLabels: Record<string, string> = {
    initial: '初始生成', devils_advocate: '反思审查', user_edit: '用户编辑', evidence_gap: '证据缺口',
  };
  return (
    <div>
      {revisions.map((rev, i) => (
        <div key={rev.revision_id} style={{ marginBottom: '16px', borderLeft: '3px solid #3b82f6', paddingLeft: '12px' }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
            <strong>{rev.revision_id}</strong>
            <span style={{ fontSize: '11px', padding: '2px 6px', borderRadius: '4px', background: '#eff6ff', color: '#3b82f6' }}>
              {sourceLabels[rev.revision_source] || rev.revision_source}
            </span>
            {rev.parent_revision_id && <span style={{ fontSize: '12px', color: '#94a3b8' }}>← {rev.parent_revision_id}</span>}
          </div>
          {rev.nick_model_name && <div style={{ fontWeight: 600, fontSize: '14px' }}>{rev.nick_model_name}</div>}
          {rev.narrative_summary && <p style={{ fontSize: '13px', color: '#64748b' }}>{rev.narrative_summary.slice(0, 300)}...</p>}
          {rev.revision_reason && <p style={{ fontSize: '12px', color: '#f59e0b' }}>原因: {rev.revision_reason}</p>}
          {rev.diff && (rev.diff.changed?.length || rev.diff.added?.length || rev.diff.removed?.length) ? (
            <div style={{ fontSize: '12px', padding: '4px 8px', background: '#f8fafc', borderRadius: '4px' }}>
              {rev.diff.changed?.map((c: any, j: number) => <div key={`c${j}`}>变更: {c.field}</div>)}
              {rev.diff.added?.map((a: any, j: number) => <div key={`a${j}`} style={{ color: '#22c55e' }}>+ {a.field}</div>)}
              {rev.diff.removed?.map((r: any, j: number) => <div key={`r${j}`} style={{ color: '#ef4444' }}>- {r.field}</div>)}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
```

#### Fix 1.5: DAG 可视化组件

**文件**：`apps/web-react/src/components/reports/DagView.tsx`（新建）

```tsx
interface DagData {
  nodes: Array<{ id: string; title: string; effort: string }>;
  edges: Array<{ from: string; to: string }>;
  milestones: Array<{ id: string; packages: string[]; label: string }>;
  has_cycle: boolean;
}

export function DagView({ dag }: { dag: DagData }) {
  if (!dag || !dag.milestones) return null;
  return (
    <div>
      {dag.has_cycle && <div style={{ color: '#ef4444', marginBottom: '8px' }}>⚠️ 检测到循环依赖</div>}
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
```

#### Fix 1.6: Binding Validation 组件

**文件**：`apps/web-react/src/components/reports/BindingValidation.tsx`（新建）

```tsx
interface BindingData {
  valid: boolean;
  issues?: Array<{ type: string; message: string }>;
  needs_evidence_items?: string[];
  orphan_packages?: string[];
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
    </div>
  );
}
```

#### Fix 1.7: Workbench 报告区整合

**文件**：`apps/web-react/src/pages/Workbench.tsx`

替换报告区的 raw JSON `<pre>` 为结构化组件分发：

```tsx
import { FeasibilityReport } from '../components/reports/FeasibilityReport';
import { ReviewReport } from '../components/reports/ReviewReport';
import { InnovationReport } from '../components/reports/InnovationReport';
import { NarrativeRevisions } from '../components/reports/NarrativeRevisions';
import { DagView } from '../components/reports/DagView';
import { BindingValidation } from '../components/reports/BindingValidation';

// 替换 REPORT_SECTIONS 渲染逻辑：
// 1. feasibility_report → <FeasibilityReport data={data} />
// 2. review_report → <ReviewReport data={data} />
// 3. innovation_points → <InnovationReport data={{innovation_points: data}} />
// 4. research_narrative → 叙事摘要 + <NarrativeRevisions revisions={finalState.narrative_revisions} />
// 5. work_packages → 工作包列表 + <DagView dag={finalState.low_bar_review?.dag} />
// 6. low_bar_review → <BindingValidation data={finalState.low_bar_review?.binding_validation} />
// 7. 其余 sections 保留 <pre> JSON fallback
```

---

### Phase 2：Workbench RAG 上下文整合 — 1h

#### Fix 2.1: Workbench 追加 RAG 问答区

**文件**：`apps/web-react/src/pages/Workbench.tsx`

在报告折叠区之后追加 RAG 问答区：

```tsx
// 当 case 完成后，显示 RAG 问答入口
{state.phase === 'done' && state.caseId && (
  <RagContextSection caseId={state.caseId} />
)}
```

**文件**：`apps/web-react/src/components/RagContextSection.tsx`（新建）

```tsx
import { useState } from 'react';
import { LoadingDots } from './LoadingDots';

export function RagContextSection({ caseId }: { caseId: string }) {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [hasIndex, setHasIndex] = useState<boolean | null>(null);

  // Check if RAG index exists for this case
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
    } catch (e) {
      setError('网络错误');
    }
    setLoading(false);
  };

  return (
    <details className="report-section">
      <summary>📚 RAG 问答</summary>
      <div className="report-content">
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
          </div>
        )}
        {error && <p style={{ color: '#ef4444', fontSize: '14px' }}>{error}</p>}
      </div>
    </details>
  );
}
```

---

### Phase 3：多文档 RAG 索引 — 1.5h

#### Fix 3.1: `indexer.py` 追加 `merge_index`

**文件**：`apps/api/app/services/rag/indexer.py`

```python
def merge_index(
    case_id: str,
    new_chunks: list[dict[str, Any]],
    source: str = "",
    case_dir: Path | None = None,
) -> dict[str, Any]:
    """Merge new chunks into existing RAG index.

    If no existing index, creates a new one (same as build_index).
    If existing index exists, appends chunks and rebuilds TF-IDF.
    """
    existing = load_index(case_id, case_dir)
    if existing is None:
        return build_index(case_id, new_chunks, source=source, case_dir=case_dir)

    # Append new chunks with offset chunk_id
    existing_n = existing.get("n_chunks", 0)
    for i, chunk in enumerate(new_chunks):
        chunk["chunk_id"] = f"chunk-{existing_n + i}"
        chunk["source"] = chunk.get("source", source)
        chunk["case_id"] = case_id

    all_chunks = existing.get("documents", []) + new_chunks
    # Rebuild vocabulary + TF-IDF (new docs change IDF)
    vocabulary = _build_vocabulary(all_chunks)
    tfidf_vectors = _compute_tfidf(all_chunks, vocabulary)

    index = {
        "case_id": case_id,
        "documents": all_chunks,
        "vocabulary": vocabulary,
        "tfidf_vectors": tfidf_vectors,
        "n_chunks": len(all_chunks),
        "n_terms": len(vocabulary),
        "created_at": existing.get("created_at", time.time()),
        "source": existing.get("source", "") + f"; {source}",
    }

    index_path = (case_dir or Path(f"tmp_re13_eval/{case_id}")) / "rag_index.json"
    atomic_write_json(index_path, index)

    return {
        "status": "ok",
        "case_id": case_id,
        "n_chunks": len(all_chunks),
        "n_new_chunks": len(new_chunks),
        "n_terms": len(vocabulary),
        "index_path": str(index_path),
    }
```

#### Fix 3.2: ACP `ingest_pdf` 支持追加

**文件**：`apps/api/app/services/acp/server.py`

修改 `_h_ingest_pdf` 使用 `merge_index`：

```python
def _h_ingest_pdf(self, params: dict[str, Any]) -> dict[str, Any]:
    from apps.api.app.services.rag.pdf_extractor import extract_pdf_from_url
    from apps.api.app.services.rag.chunker import chunk_text
    from apps.api.app.services.rag.indexer import merge_index  # changed from build_index

    case_id = params.get("case_id", "global")
    pdf_url = params["pdf_url"]

    result = extract_pdf_from_url(pdf_url)
    if result["status"] != "ok":
        return result

    chunks = chunk_text(result["text"])
    if not chunks:
        return {"status": "extraction_failed", "reason": "no chunks generated"}

    return merge_index(case_id, chunks, source=pdf_url)  # merge instead of build
```

#### Fix 3.3: 测试

**文件**：`apps/api/tests/test_re46_merge_index.py`（新建）

```python
"""Re4.6: Multi-document RAG merge index tests."""
from __future__ import annotations

from pathlib import Path

from apps.api.app.services.rag.indexer import build_index, load_index, merge_index


class TestMergeIndex:
    def test_merge_creates_new_if_no_existing(self, tmp_path: Path):
        """merge_index with no existing index should create new."""
        chunks = [{"text": "YOLO detection", "chunk_id": "chunk-0"}]
        result = merge_index("test", chunks, source="url1", case_dir=tmp_path / "test")
        assert result["status"] == "ok"
        assert result["n_chunks"] == 1

    def test_merge_appends_to_existing(self, tmp_path: Path):
        """merge_index should append to existing index."""
        # Create initial
        chunks1 = [{"text": "YOLO detection model", "chunk_id": "chunk-0"}]
        build_index("test2", chunks1, source="url1", case_dir=tmp_path / "test2")

        # Merge second
        chunks2 = [{"text": "Dataset NEU-DET", "chunk_id": "chunk-0"}]
        result = merge_index("test2", chunks2, source="url2", case_dir=tmp_path / "test2")
        assert result["status"] == "ok"
        assert result["n_chunks"] == 2
        assert result["n_new_chunks"] == 1

        # Verify loaded index has both
        loaded = load_index("test2", case_dir=tmp_path / "test2")
        assert loaded["n_chunks"] == 2
        sources = [d["source"] for d in loaded["documents"]]
        assert "url1" in sources
        assert "url2" in sources

    def test_merge_rebuilds_tfidf(self, tmp_path: Path):
        """Merge should rebuild TF-IDF with updated IDF."""
        chunks1 = [{"text": "YOLO YOLO detection", "chunk_id": "chunk-0"}]
        build_index("test3", chunks1, source="url1", case_dir=tmp_path / "test3")

        chunks2 = [{"text": "Transformer architecture", "chunk_id": "chunk-0"}]
        merge_index("test3", chunks2, source="url2", case_dir=tmp_path / "test3")

        loaded = load_index("test3", case_dir=tmp_path / "test3")
        assert len(loaded["tfidf_vectors"]) == 2
        # "yolo" should have different IDF after adding transformer doc
        assert "yolo" in loaded["vocabulary"]
        assert "transformer" in loaded["vocabulary"]

    def test_merge_chunk_ids_unique(self, tmp_path: Path):
        """Merged chunks should have unique IDs."""
        chunks1 = [{"text": "first document", "chunk_id": "chunk-0"}]
        build_index("test4", chunks1, case_dir=tmp_path / "test4")

        chunks2 = [{"text": "second document", "chunk_id": "chunk-0"}]
        merge_index("test4", chunks2, case_dir=tmp_path / "test4")

        loaded = load_index("test4", case_dir=tmp_path / "test4")
        ids = [d["chunk_id"] for d in loaded["documents"]]
        assert len(ids) == len(set(ids))  # no duplicates
```

---

### Phase 4：首页增强 — 30min

#### Fix 4.1: 历史卡片显示 topic + score

**文件**：`apps/web-react/src/pages/Home.tsx`

修改历史列表渲染：

```tsx
// 在 listCases() 后，对每个 case 追加加载 state 摘要
// 修改 history-item 渲染：
<div key={item.case_id} className="history-item" onClick={() => loadHistory(item.case_id)}>
  <div>
    <div className="case-id">{item.case_id}</div>
    {item.topic && <div style={{ fontSize: '13px', color: '#1a202c' }}>{item.topic.slice(0, 50)}</div>}
  </div>
  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
    {item.score !== undefined && (
      <span style={{ fontSize: '12px', fontWeight: 600, color: item.score >= 75 ? '#22c55e' : item.score >= 50 ? '#f59e0b' : '#ef4444' }}>
        {item.score}
      </span>
    )}
    <span className={`case-status ${item.status}`}>{item.status}</span>
  </div>
</div>
```

需要在 `listCases` 返回后批量加载每个 case 的 state 摘要（只取 topic + feasibility score）：

```tsx
useEffect(() => {
  listCases().then(async (data) => {
    const cases = (data.cases || []).slice(0, 10);
    // Batch load topic + score for each case
    const enriched = await Promise.all(
      cases.map(async (c: CaseItem) => {
        try {
          const resp = await fetch(`/api/v1/research/${c.case_id}/state`);
          if (resp.ok) {
            const state = await resp.json();
            return { ...c, topic: state.topic, score: state.feasibility_report?.score };
          }
        } catch {}
        return c;
      })
    );
    setHistory(enriched);
  }).catch(() => {});
}, []);
```

---

### Phase 5：Vite 构建 + Playwright 回归 — 1.5h

#### Fix 5.1: 构建验证

```bash
cd apps/web-react
npm run build
# 预期：tsc 零 error，dist/ 产出
```

#### Fix 5.2: Playwright 测试更新

**文件**：`apps/web-react/e2e/test_re42_react_web.py`

更新已有测试 + 追加结构化报告验证：

```python
class TestReactWorkbenchReport:
    def test_completed_case_feasibility_rendered(self, page: Page):
        """已完成 case 的可行性报告应结构化渲染。"""
        page.goto(BASE_URL + "/#/workbench/re41-verify-001")
        page.wait_for_timeout(3000)
        # Should NOT be raw JSON pre — should have structured UI
        # Look for feasibility score as a large number
        expect(page.locator("text=可行性评估")).to_be_visible()
        page.screenshot(path=str(SCREENSHOT_DIR / "workbench_feasibility.png"))

    def test_completed_case_innovation_rendered(self, page: Page):
        """创新点应结构化渲染，显示 candidate_ids + scores。"""
        page.goto(BASE_URL + "/#/workbench/re43-verify-001")
        page.wait_for_timeout(3000)
        expect(page.locator("text=创新点")).to_be_visible()
        page.screenshot(path=str(SCREENSHOT_DIR / "workbench_innovation.png"))

    def test_completed_case_dag_rendered(self, page: Page):
        """DAG 应显示里程碑分层。"""
        page.goto(BASE_URL + "/#/workbench/re43-verify-001")
        page.wait_for_timeout(3000)
        # Expand work packages section
        page.click("text=工作包")
        page.wait_for_timeout(500)
        page.screenshot(path=str(SCREENSHOT_DIR / "workbench_dag.png"))

    def test_home_history_shows_topic(self, page: Page):
        """首页历史卡片应显示 topic 摘要。"""
        page.goto(BASE_URL + "/")
        page.wait_for_timeout(3000)
        # History items should have topic text (not just case_id)
        page.screenshot(path=str(SCREENSHOT_DIR / "home_history_enriched.png"))
```

---

### Phase 6：RAG 页面多文档支持 — 30min

#### Fix 6.1: RAG 页面显示已入库文档列表

**文件**：`apps/web-react/src/pages/RagPlaceholder.tsx`

追加已入库文档列表展示：

```tsx
// 在入库成功后，显示已入库文档列表
{ingestResult && ingestResult.status === 'ok' && (
  <div style={{ marginTop: '8px', fontSize: '13px', color: '#64748b' }}>
    ✅ 入库成功：{ingestResult.n_chunks} 个文本块
    {ingestResult.n_new_chunks && `（新增 ${ingestResult.n_new_chunks} 块）`}
    ，共 {ingestResult.n_terms} 个词项
  </div>
)}

// 追加"已入库文档"列表（从 knowledge graph nodes 的 paper 类型获取）
```

#### Fix 6.2: 入库提示文案

当已有 index 时，入库按钮文案改为"追加入库"：

```tsx
<button ...>
  {ingesting ? <LoadingDots text="入库中" /> : (hasIndex ? '追加入库' : '入库')}
</button>
```

---

### Phase 7：验收与端到端验证 — 1h

#### Step 1: TypeScript 构建

```bash
cd apps/web-react
npm run build
# 预期：tsc 零 error
```

#### Step 2: pytest 收集不退化

```bash
cd G:\PaperAgent
.venv\Scripts\python.exe -m pytest --collect-only -q 2>&1 | findstr "collected error"
# 预期：0 errors，collected 数 ≥ 527
```

#### Step 3: ruff 无新增

```bash
.venv\Scripts\python.exe -m ruff check apps/api/app --statistics
# 预期：≤ 19 errors（无新增）
```

#### Step 4: 多文档 RAG 端到端验证

```bash
# 启动后端
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181

# 1. 入库第一个 PDF
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" -H "X-ACP-Capability: write" \
  -d '{"capability":"ingest_pdf","params":{"pdf_url":"https://arxiv.org/pdf/2401.17270","case_id":"re46-test"}}'

# 2. 入库第二个 PDF (追加)
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" -H "X-ACP-Capability: write" \
  -d '{"capability":"ingest_pdf","params":{"pdf_url":"https://arxiv.org/pdf/2211.15444","case_id":"re46-test"}}'

# 3. 查询（应能检索到两篇文档的 chunks）
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability":"query_rag","params":{"question":"What methods are used?","case_id":"re46-test"}}'

# 4. 知识图谱（应包含两篇论文的节点）
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability":"get_knowledge_graph","params":{"case_id":"re46-test"}}'
```

#### Step 5: Playwright 截图

```bash
# 启动 Vite dev server
cd apps/web-react && npm run dev

# 运行 e2e
.venv\Scripts\python.exe -m pytest apps/web-react/e2e/test_re42_react_web.py -v -m "react_web"
```

**产物完整性检查清单**：

| 检查项 | 通过标准 |
|---|---|
| tsc 零 error | `npm run build` 成功 |
| 报告区结构化 | 可行性显示分数+verdict，不再 raw JSON |
| binding_validation 展示 | issues + needs_evidence 可见 |
| narrative_revisions 时间线 | revision_id → diff 链可见 |
| DAG 里程碑分层 | milestones 按 阶段 1/2/... 排列 |
| 多文档 RAG | 第二次 ingest_pdf 返回 n_new_chunks > 0 |
| 检索覆盖多文档 | query_rag 的 retrieved_chunks 包含不同 source |
| 首页历史卡片 | 显示 topic 摘要 + score |
| pytest collection | 0 errors, ≥ 527 collected |
| ruff | ≤ 19 errors |
| Playwright 截图 | 新增 feasibility/innovation/dag/home 截图 |

> **自我检验**：验收者必须对照上述清单逐项检查实际产物，
> 确认每项通过后再标记 Phase 7 完成。

---

## 3. 执行顺序与依赖

```
Phase 1 (报告组件) ─── 无依赖
    │
    ├── Phase 2 (Workbench RAG 整合) ─── 依赖 Phase 1
    │
    ├── Phase 3 (多文档 RAG) ─── 无依赖（后端）
    │
    ├── Phase 4 (首页增强) ─── 无依赖
    │
    ├── Phase 5 (构建 + Playwright) ─── 依赖 Phase 1+2+4
    │
    ├── Phase 6 (RAG 页面多文档) ─── 依赖 Phase 3
    │
    └── Phase 7 (验收 + 端到端) ─── 依赖全部完成

可并行：
- Phase 3 (后端 merge_index) 和 Phase 1 (前端组件) 完全并行
- Phase 4 (首页) 和 Phase 2 (Workbench RAG) 可并行
```

---

## 4. 风险与预案

| 风险 | 触发信号 | 预案 |
|---|---|---|
| 首页批量加载 state 导致慢 | 10 个 case × 300KB state.json = 3MB | 只取 topic + feasibility_report.score 两个字段；或后端新增轻量 `/summary` 端点 |
| TypeScript strict 报错 | tsc 失败 | 新组件用 `any` 类型过渡，后续 Day 7 收紧 |
| 多文档 merge 后 chunk_id 冲突 | 重复 chunk_id | merge_index 自动偏移：`chunk-{existing_n + i}` |
| DAG 无 milestones（空 packages） | work_packages 为空 | DagView 组件判空处理 |
| Playwright 截图时 case 未加载完 | timeout | wait_for_timeout 增至 5s |

---

## 5. 完成标准

- [ ] 报告区不再 raw JSON dump，每个 section 有结构化 UI
- [ ] feasibility 显示分数 + verdict + 降级路径
- [ ] review 显示维度评分 + evidence_critiques
- [ ] innovation 显示 candidate_ids + scores + needs_evidence 标记
- [ ] narrative_revisions 时间线显示 revision_id → diff
- [ ] DAG 里程碑分层可见
- [ ] binding_validation 的 issues + needs_evidence 可见
- [ ] Workbench 完成后有 RAG 问答入口
- [ ] 多文档 RAG：`merge_index` 可追加，chunk_id 不冲突
- [ ] 首页历史卡片显示 topic + score
- [ ] `npm run build` 零 TypeScript error
- [ ] `pytest --collect-only` 零 error
- [ ] `ruff check apps/api/app` ≤ 19 errors
- [ ] **端到端验证**：多 PDF 入库 → 查询覆盖多源 → 知识图谱多论文节点
- [ ] Playwright 截图生成

---

## 6. 提交清单

| 文件 | 操作 |
|---|---|
| `apps/web-react/src/components/reports/FeasibilityReport.tsx` | 新建 |
| `apps/web-react/src/components/reports/ReviewReport.tsx` | 新建 |
| `apps/web-react/src/components/reports/InnovationReport.tsx` | 新建 |
| `apps/web-react/src/components/reports/NarrativeRevisions.tsx` | 新建 |
| `apps/web-react/src/components/reports/DagView.tsx` | 新建 |
| `apps/web-react/src/components/reports/BindingValidation.tsx` | 新建 |
| `apps/web-react/src/components/RagContextSection.tsx` | 新建 |
| `apps/web-react/src/pages/Workbench.tsx` | 修改：结构化报告 + RAG 上下文 |
| `apps/web-react/src/pages/Home.tsx` | 修改：历史卡片增强 |
| `apps/web-react/src/pages/RagPlaceholder.tsx` | 修改：多文档提示 |
| `apps/api/app/services/rag/indexer.py` | 修改：追加 `merge_index` |
| `apps/api/app/services/acp/server.py` | 修改：`ingest_pdf` 用 `merge_index` |
| `apps/api/tests/test_re46_merge_index.py` | 新建 |
| `apps/web-react/e2e/test_re42_react_web.py` | 修改：追加报告截图测试 |
| `CHANGELOG.md` | 追加 Re4.6 条目 |

---

## 7. CHANGELOG 预备

```markdown
## [0.4.0-dev] - 2026-07-10 (Re4.6)

### Added
- 7 个结构化报告组件：FeasibilityReport、ReviewReport（含 evidence_critiques）、
  InnovationReport（含 candidate_ids + scores + needs_evidence）、NarrativeRevisions（含 diff 时间线）、
  DagView（里程碑分层）、BindingValidation（issues + needs_evidence）、RagContextSection
- `indexer.py`: `merge_index` 函数，支持多 PDF 追加入库 + TF-IDF 重建
- `test_re46_merge_index.py`: 多文档合并索引测试

### Changed
- `Workbench.tsx`: 报告区从 raw JSON `<pre>` 替换为结构化组件
- `Workbench.tsx`: 追加 RAG 问答折叠区（完成后可对 case PDF 提问）
- `Home.tsx`: 历史卡片显示 topic 摘要 + feasibility score
- `RagPlaceholder.tsx`: 多文档提示 + 追加入库文案
- `acp/server.py`: `ingest_pdf` 改用 `merge_index`（支持追加）

### Verified
- 端到端多文档 RAG：2 篇 arXiv PDF 入库 → query_rag 检索覆盖双源 → 知识图谱多论文节点
- 前端报告结构化：feasibility/review/innovation/narrative/DAG/binding 各有专用 UI
- Playwright 截图：feasibility/innovation/dag/home 回归通过
```
