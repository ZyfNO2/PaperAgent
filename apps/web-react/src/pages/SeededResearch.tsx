import { useState } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import type {
  CandidateSeedInput,
  SeedInputForm,
  SeedRole,
  RunMode,
  NetworkPolicy,
  SeededDemoResult,
  GateResult,
  FusedVerdict,
} from '../types/seededResearch';

// ===== 常量映射 =====

const INPUT_FORM_OPTIONS: { value: SeedInputForm; label: string; placeholder: string }[] = [
  { value: 'doi', label: 'DOI', placeholder: '10.1000/xyz123' },
  { value: 'arxiv', label: 'arXiv', placeholder: '2106.04561' },
  { value: 'url', label: 'URL', placeholder: 'https://...' },
  { value: 'pdf', label: 'PDF', placeholder: '/path/to/paper.pdf' },
  { value: 'citation', label: 'Citation', placeholder: '作者. 标题. 会议, 年份' },
  { value: 'title', label: 'Title', placeholder: '论文标题' },
];

const ROLE_OPTIONS: { value: SeedRole; label: string; hint: string }[] = [
  { value: 'classic_anchor', label: '经典锚点', hint: '领域奠基性工作' },
  { value: 'current_sota_candidate', label: '当前 SOTA 候选', hint: '现有最强基线' },
  { value: 'reproduction_target', label: '复现目标', hint: '需要复现的论文' },
  { value: 'parallel_inspiration', label: '平行启发', hint: '跨领域方法借鉴' },
  { value: 'survey_reference', label: '综述参考', hint: '领域综述' },
];

const RUN_MODE_OPTIONS: { value: RunMode; label: string; desc: string }[] = [
  { value: 'full_agent', label: 'Full Agent', desc: '完整 ReAct 反思链，多轮 Gate 反思 + 决策融合（默认）' },
  { value: 'lite_chain', label: 'Lite Chain', desc: '轻量直线链，跳过反思循环，单轮直出' },
  { value: 'offline_replay', label: 'Offline Replay', desc: '离线回放模式，从已有 trace 重放，不发外部请求' },
];

const NETWORK_OPTIONS: { value: NetworkPolicy; label: string; desc: string }[] = [
  { value: 'online', label: 'Online', desc: '允许调用外部 API（Semantic Scholar / arXiv / GitHub 等）' },
  { value: 'offline', label: 'Offline', desc: '仅使用本地缓存，不发起任何外部网络请求' },
];

const GATE_LABELS: { key: keyof SeededDemoResult; label: string }[] = [
  { key: 'gate_seed_audit_gate', label: '种子核验 Gate' },
  { key: 'gate_tailor_gate', label: 'Tailor Gate' },
  { key: 'gate_final_review_gate', label: '最终评审 Gate' },
];

const VERDICT_ICON: Record<string, string> = {
  pass: '✅',
  revise: '⚠️',
  unresolved: '❌',
};

const EXISTENCE_ICON: Record<string, string> = {
  verified: '✅',
  ambiguous: '⚠️',
  not_found: '❌',
};

const FUSED_VERDICT_COLOR: Record<FusedVerdict, string> = {
  GO: 'var(--color-success)',
  CONDITIONAL: 'var(--color-primary)',
  RISKY: 'var(--color-warning)',
  BLOCKED: 'var(--color-error)',
};

// ===== 默认种子行 =====

function makeEmptySeed(idx: number): CandidateSeedInput {
  return {
    seed_id: `S${idx}`,
    input_form: 'doi',
    role: 'classic_anchor',
  };
}

// ===== 主页面 =====

export function SeededResearch() {
  // --- Section 1: 题目 + 种子录入 ---
  const [topic, setTopic] = useState('');
  const [seeds, setSeeds] = useState<CandidateSeedInput[]>([
    makeEmptySeed(1),
    makeEmptySeed(2),
  ]);

  // --- Section 2: 模式选择 ---
  const [runMode, setRunMode] = useState<RunMode>('full_agent');
  const [networkPolicy, setNetworkPolicy] = useState<NetworkPolicy>('online');

  // --- Section 3: 结果展示 ---
  const [result, setResult] = useState<SeededDemoResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // ===== 种子行操作 =====
  const updateSeed = (idx: number, patch: Partial<CandidateSeedInput>) => {
    setSeeds((prev) => prev.map((s, i) => (i === idx ? { ...s, ...patch } : s)));
  };

  const addSeed = () => {
    setSeeds((prev) => [...prev, makeEmptySeed(prev.length + 1)]);
  };

  const removeSeed = (idx: number) => {
    setSeeds((prev) => prev.filter((_, i) => i !== idx));
  };

  // ===== fixture 加载 =====
  const loadFixture = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const resp = await fetch('/fixtures/seeded_demo_vit_dr.json');
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const data = (await resp.json()) as SeededDemoResult;
      setResult(data);
      // 同步题目到 fixture 的 topic，方便对照
      if (data.topic && !topic) {
        setTopic(data.topic);
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  // ===== 导出 Final Package JSON =====
  const exportPackage = () => {
    if (!result) return;
    const payload = {
      case_key: result.case_key,
      topic: result.topic,
      mode: result.mode,
      fused_verdict: result.fused_verdict,
      fused_verdict_rationale: result.fused_verdict_rationale,
      final_research_package_sections: result.final_research_package_sections,
      seed_cards: result.seed_cards,
      gate_results: {
        seed_audit_gate: result.gate_seed_audit_gate,
        tailor_gate: result.gate_tailor_gate,
        final_review_gate: result.gate_final_review_gate,
      },
      tailored_method_summary: result.tailored_method_summary,
      hypothesis_preview: result.hypothesis_preview,
      n_ledger_entries: result.n_ledger_entries,
      gap_statuses: result.gap_statuses,
      exported_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `seeded_research_package_${result.case_key}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // ===== 渲染辅助 =====
  const renderPassTier = (label: string, pass: boolean, reasons?: string[]) => (
    <div className="pa-pass-tier">
      <span className="pa-pass-icon">{pass ? '✅' : '❌'}</span>
      <span className="pa-pass-label">{label}</span>
      {!pass && reasons && reasons.length > 0 && (
        <span className="pa-muted pa-small">（{reasons.join('；')}）</span>
      )}
    </div>
  );

  const renderGateCard = (label: string, gate: GateResult) => (
    <div className={`pa-gate-card verdict-${gate.verdict}`} key={label}>
      <div className="pa-gate-header">
        <span className="pa-gate-icon">{VERDICT_ICON[gate.verdict] ?? '❓'}</span>
        <span className="pa-gate-title">{label}</span>
        <span className="pa-gate-verdict">{gate.verdict}</span>
      </div>
      <div className="pa-small pa-muted">
        round {gate.round_idx} · generated_by {gate.generated_by}
      </div>
      <div className="pa-gate-rationale">{gate.rationale}</div>
      {gate.unresolved_gaps && gate.unresolved_gaps.length > 0 && (
        <div className="pa-small">
          未解决 gap：{gate.unresolved_gaps.join(', ')}
        </div>
      )}
      {gate.re_search_requests && gate.re_search_requests.length > 0 && (
        <div className="pa-small">
          重搜请求：{gate.re_search_requests.join(', ')}
        </div>
      )}
    </div>
  );

  // ===== 渲染 =====
  return (
    <div className="seeded-research-page">
      <div className="workbench-header">
        <div>
          <div className="workbench-topic">Seeded Research</div>
          <div className="workbench-meta">
            <span>种子驱动研究流程 · Re8.0</span>
          </div>
        </div>
      </div>

      {/* ============ Section 1: 种子录入 ============ */}
      <Card title="① 种子录入" testId="seed-intake-card">
        <div className="pa-form-row">
          <label className="pa-small pa-muted" htmlFor="seeded-topic-input">
            研究题目
          </label>
          <textarea
            id="seeded-topic-input"
            className="pa-input pa-textarea"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="例：Vision Transformer for diabetic retinopathy grading"
            rows={2}
            data-testid="seeded-topic-input"
          />
        </div>

        <div className="pa-seed-list" data-testid="seed-list">
          {seeds.map((seed, idx) => {
            const formOpt = INPUT_FORM_OPTIONS.find((o) => o.value === seed.input_form);
            return (
              <div className="pa-seed-row" key={idx} data-testid={`seed-row-${idx}`}>
                <span className="pa-seed-id">{seed.seed_id}</span>
                <select
                  className="pa-input pa-seed-select"
                  value={seed.input_form}
                  onChange={(e) => updateSeed(idx, { input_form: e.target.value as SeedInputForm })}
                  aria-label="输入形式"
                >
                  {INPUT_FORM_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                <input
                  className="pa-input pa-seed-identifier"
                  value={
                    seed.doi ?? seed.arxiv_id ?? seed.url ?? seed.title ?? seed.pdf_path ?? ''
                  }
                  onChange={(e) => {
                    const val = e.target.value;
                    const form = seed.input_form;
                    if (form === 'doi') updateSeed(idx, { doi: val });
                    else if (form === 'arxiv') updateSeed(idx, { arxiv_id: val });
                    else if (form === 'url') updateSeed(idx, { url: val });
                    else if (form === 'pdf') updateSeed(idx, { pdf_path: val });
                    else updateSeed(idx, { title: val });
                  }}
                  placeholder={formOpt?.placeholder ?? '标识符'}
                  aria-label="种子标识符"
                />
                <select
                  className="pa-input pa-seed-select"
                  value={seed.role}
                  onChange={(e) => updateSeed(idx, { role: e.target.value as SeedRole })}
                  aria-label="种子角色"
                >
                  {ROLE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => removeSeed(idx)}
                  disabled={seeds.length <= 1}
                  data-testid={`seed-remove-${idx}`}
                >
                  删除
                </Button>
              </div>
            );
          })}
        </div>

        <div className="pa-interview-actions">
          <Button variant="secondary" size="sm" onClick={addSeed} data-testid="seed-add">
            + 添加种子
          </Button>
        </div>

        <div className="pa-small pa-muted" style={{ marginTop: '8px' }}>
          当前 {seeds.length} 个种子 · 题目：{topic.trim() || '（未填写）'}
        </div>
      </Card>

      {/* ============ Section 2: 模式选择 ============ */}
      <Card title="② 运行模式" testId="seeded-mode-card">
        <div className="pa-form-row">
          <label className="pa-small pa-muted">RunMode</label>
          <div className="pa-radio-group" role="radiogroup" aria-label="运行模式">
            {RUN_MODE_OPTIONS.map((opt) => (
              <label key={opt.value} className="pa-radio-label">
                <input
                  type="radio"
                  name="run-mode"
                  value={opt.value}
                  checked={runMode === opt.value}
                  onChange={() => setRunMode(opt.value)}
                />
                <span className="pa-radio-text">
                  <strong>{opt.label}</strong>
                  <span className="pa-muted pa-small"> — {opt.desc}</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="pa-form-row">
          <label className="pa-small pa-muted">NetworkPolicy</label>
          <div className="pa-radio-group" role="radiogroup" aria-label="网络策略">
            {NETWORK_OPTIONS.map((opt) => (
              <label key={opt.value} className="pa-radio-label">
                <input
                  type="radio"
                  name="network-policy"
                  value={opt.value}
                  checked={networkPolicy === opt.value}
                  onChange={() => setNetworkPolicy(opt.value)}
                />
                <span className="pa-radio-text">
                  <strong>{opt.label}</strong>
                  <span className="pa-muted pa-small"> — {opt.desc}</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="pa-small pa-muted" style={{ marginTop: '8px' }}>
          已选：{runMode} · {networkPolicy}
        </div>
      </Card>

      {/* ============ Section 3: 结果展示 ============ */}
      <Card title="③ 结果展示（fixture 联调）" testId="seeded-result-card">
        <div className="pa-interview-actions">
          <Button
            variant="primary"
            size="sm"
            onClick={loadFixture}
            disabled={loading}
            data-testid="seeded-load-fixture"
          >
            {loading ? '加载中…' : '加载 fixture 结果'}
          </Button>
          {result && (
            <Button
              variant="secondary"
              size="sm"
              onClick={exportPackage}
              data-testid="seeded-export-package"
            >
              导出 Final Package JSON
            </Button>
          )}
        </div>

        {loadError && (
          <div className="status-banner error" style={{ marginTop: '12px' }}>
            <span className="status-icon">❌</span>
            <div className="status-text">
              <div className="status-label">fixture 加载失败</div>
              <div className="status-counts">{loadError}</div>
            </div>
          </div>
        )}

        {result && (
          <div className="pa-result-area" data-testid="seeded-result-area">
            {/* 三层 PASS 摘要 */}
            <div className="pa-pass-tiers" data-testid="pass-tiers">
              {renderPassTier('runtime_pass', result.runtime_pass)}
              {renderPassTier('contract_pass', result.contract_pass, result.contract_pass_reasons)}
              {renderPassTier('quality_pass', result.quality_pass, result.quality_pass_reasons)}
            </div>

            {/* 种子核验状态表 */}
            <details className="report-section" open>
              <summary>🌱 种子核验状态（{result.seed_cards.length}）</summary>
              <div className="report-content">
                <table className="snapshot-table">
                  <thead>
                    <tr>
                      <th>seed_id</th>
                      <th>resolved_title</th>
                      <th>existence_status</th>
                      <th>role</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.seed_cards.map((c) => (
                      <tr key={c.seed_id}>
                        <td>{c.seed_id}</td>
                        <td>{c.resolved_title}</td>
                        <td>
                          {EXISTENCE_ICON[c.existence_status] ?? '❓'} {c.existence_status}
                        </td>
                        <td>{c.role}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>

            {/* 3 Gate Verdicts */}
            <details className="report-section" open>
              <summary>🚦 Reflection Gates（3）</summary>
              <div className="report-content">
                <div className="pa-gate-grid">
                  {GATE_LABELS.map(({ key, label }) => {
                    const gate = result[key] as GateResult;
                    return renderGateCard(label, gate);
                  })}
                </div>
              </div>
            </details>

            {/* Fused Verdict */}
            <details className="report-section" open>
              <summary>🎯 Decision Fusion</summary>
              <div className="report-content">
                <div
                  className="pa-fused-verdict"
                  style={{ color: FUSED_VERDICT_COLOR[result.fused_verdict] }}
                  data-testid="fused-verdict"
                >
                  {result.fused_verdict}
                </div>
                {result.fused_verdict_rationale && (
                  <div className="pa-muted" style={{ marginTop: '6px' }}>
                    {result.fused_verdict_rationale}
                  </div>
                )}
              </div>
            </details>

            {/* Evidence Gaps */}
            <details className="report-section">
              <summary>🔍 Evidence Gaps（{result.n_evidence_gaps ?? 0}）</summary>
              <div className="report-content">
                {result.gap_statuses && (
                  <div className="pa-small pa-muted" style={{ marginBottom: '8px' }}>
                    状态分布：{Object.entries(result.gap_statuses).map(([k, v]) => `${k}=${v}`).join(' · ')}
                  </div>
                )}
                <div className="pa-small pa-muted">
                  共 {result.n_evidence_gaps ?? 0} 个 gap（fixture 摘要未含逐条 gap 详情，详见完整 package）。
                </div>
              </div>
            </details>

            {/* Tailored Method */}
            <details className="report-section">
              <summary>✂️ Tailored Method</summary>
              <div className="report-content">
                <table className="snapshot-table">
                  <tbody>
                    <tr>
                      <td><strong>core_method</strong></td>
                      <td>{result.tailored_method_summary.core_method || '（空）'}</td>
                    </tr>
                    <tr>
                      <td><strong>contribution_type</strong></td>
                      <td>{result.tailored_method_summary.contribution_type ?? '（未设置）'}</td>
                    </tr>
                    <tr>
                      <td><strong>baseline_model</strong></td>
                      <td>{result.tailored_method_summary.baseline_model ?? '（未设置）'}</td>
                    </tr>
                    <tr>
                      <td><strong>tailored_verdict</strong></td>
                      <td>{result.tailored_verdict ?? '—'}</td>
                    </tr>
                    <tr>
                      <td><strong>ablation_rows</strong></td>
                      <td>{result.tailored_ablation_rows ?? 0}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </details>

            {/* Final Research Package 7 section 检查清单 */}
            <details className="report-section" open>
              <summary>📦 Final Research Package（{result.final_research_package_sections.length}/7 section）</summary>
              <div className="report-content">
                <ul className="pa-checklist">
                  {result.final_research_package_sections.map((sec) => (
                    <li key={sec} className="pa-checklist-item">
                      <span className="pa-pass-icon">✅</span>
                      <span>{sec}</span>
                    </li>
                  ))}
                  {(result.final_research_package_missing_sections ?? []).map((sec) => (
                    <li key={sec} className="pa-checklist-item">
                      <span className="pa-pass-icon">❌</span>
                      <span className="pa-muted">{sec}（缺失）</span>
                    </li>
                  ))}
                </ul>
                <div className="pa-small pa-muted" style={{ marginTop: '8px' }}>
                  ledger 条目：{result.n_ledger_entries ?? 0} · trace 事件：{result.n_trace_events ?? 0} · react actions：{result.n_react_actions ?? 0}
                </div>
              </div>
            </details>

            {/* 可证伪假设预览 */}
            {result.hypothesis_preview && (
              <details className="report-section">
                <summary>🧪 Falsifiable Hypothesis</summary>
                <div className="report-content">
                  <p className="pa-small">{result.hypothesis_preview}</p>
                </div>
              </details>
            )}

            {/* 运行元信息 */}
            <details className="report-section">
              <summary>📋 运行元信息</summary>
              <div className="report-content">
                <table className="snapshot-table">
                  <tbody>
                    <tr><td><strong>case_key</strong></td><td>{result.case_key}</td></tr>
                    <tr><td><strong>mode</strong></td><td>{result.mode}</td></tr>
                    <tr><td><strong>status</strong></td><td>{result.status}</td></tr>
                    <tr><td><strong>elapsed_s</strong></td><td>{result.elapsed_s}</td></tr>
                    <tr><td><strong>n_errors</strong></td><td>{result.n_errors ?? 0}</td></tr>
                    {result.error_samples && result.error_samples.length > 0 && (
                      <tr><td><strong>error_samples</strong></td><td>{result.error_samples.join(', ')}</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </details>
          </div>
        )}

        {!result && !loading && !loadError && (
          <div className="empty-state" style={{ padding: '24px' }}>
            <div className="empty-icon">📭</div>
            <div className="empty-title">尚未加载结果</div>
            <div className="empty-desc">点击「加载 fixture 结果」查看 Seeded Research 运行产物（静态联调，不接真实 API）</div>
          </div>
        )}
      </Card>
    </div>
  );
}
