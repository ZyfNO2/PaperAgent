import { useState } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { ErrorState } from '../components/ErrorState';
import {
  submitSeededResearch,
  getSeededSummary,
  pollCaseStatus,
} from '../lib/api';
import type {
  CandidateSeedInput,
  SeedInputForm,
  SeedRole,
  RunMode,
  NetworkPolicy,
  SeededDemoResult,
  GateResult,
  GateVerdict,
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

// Re8.2 WP3: Seed Audit Gate structured reason code labels
const REASON_CODE_LABELS: Record<string, string> = {
  SEED_NOT_FOUND: '未找到匹配种子',
  SEED_LOW_CONFIDENCE: '候选置信度不足',
  SEED_SOURCE_CONFLICT: '多源信息冲突',
  SEED_AUTHOR_MISMATCH: '作者信息不一致',
  SEED_YEAR_MISMATCH: '年份信息不一致',
  SEED_IDENTIFIER_CONFLICT: '标识符冲突',
  SEED_FULLTEXT_UNAVAILABLE: '全文无法获取',
  SEED_VERIFIED: '种子已核验',
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

  // Re8.1 WP5: live result from real backend API (replaces fixture-only flow)
  const [liveResult, setLiveResult] = useState<SeededDemoResult | null>(null);
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [liveCaseId, setLiveCaseId] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<string>('');
  const [liveStatusMessage, setLiveStatusMessage] = useState<string>('');

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

  // ===== Re8.1 WP5: 真实后端 API 调用 =====
  const runRealResearch = async () => {
    const trimmedTopic = topic.trim();
    if (!trimmedTopic) {
      setLiveError('请先填写研究题目');
      return;
    }
    // Validate seeds: at least one identifier per seed
    for (let i = 0; i < seeds.length; i++) {
      const s = seeds[i];
      const hasId = !!(
        s.doi?.trim() ||
        s.arxiv_id?.trim() ||
        s.url?.trim() ||
        s.title?.trim() ||
        s.pdf_path?.trim()
      );
      if (!hasId) {
        setLiveError(`种子 ${s.seed_id || `S${i + 1}`} 缺少标识符（DOI/arXiv/URL/title/PDF 必须有一个）`);
        return;
      }
    }

    setLiveLoading(true);
    setLiveError(null);
    setLiveResult(null);
    setLiveStatus('submitting');
    setLiveStatusMessage('正在提交到真实后端...');

    try {
      const submitResp = await submitSeededResearch({
        topic: trimmedTopic,
        seeds: seeds.map((s) => ({
          seed_id: s.seed_id,
          input_form: s.input_form,
          doi: s.doi || undefined,
          arxiv_id: s.arxiv_id || undefined,
          url: s.url || undefined,
          title: s.title || undefined,
          pdf_path: s.pdf_path || undefined,
          authors: s.authors,
          year: s.year,
          role: s.role,
        })),
        run_mode: runMode,
        network_policy: networkPolicy,
      });
      setLiveCaseId(submitResp.case_id);
      setLiveStatus('running');
      setLiveStatusMessage(
        `后端已接受（case_id=${submitResp.case_id}, ${submitResp.n_seeds} 个种子, ${submitResp.run_mode}/${submitResp.network_policy}）。轮询进度...`,
      );

      // Poll until done/error (default 10 min timeout)
      await pollCaseStatus(submitResp.case_id, {
        intervalMs: 3000,
        timeoutMs: 1_800_000, // 30 min: real full_agent pipeline can exceed 10 min
        onUpdate: (st) => {
          const s = String(st.status || 'running');
          setLiveStatus(s);
          const currentNode = st.current_node ? ` · 当前节点: ${String(st.current_node)}` : '';
          const elapsed = st.elapsed_s ? ` · 已运行 ${String(st.elapsed_s)}s` : '';
          setLiveStatusMessage(`状态: ${s}${currentNode}${elapsed}`);
        },
      });

      setLiveStatus('fetching');
      setLiveStatusMessage('运行完成，正在拉取结果摘要...');
      const summary = await getSeededSummary(submitResp.case_id);
      setLiveResult(summary as unknown as SeededDemoResult);
      setLiveStatus('done');
      setLiveStatusMessage(`完成，用时 ${Number(summary.elapsed_s || 0).toFixed(0)}s`);
    } catch (err) {
      setLiveStatus('error');
      setLiveError(err instanceof Error ? err.message : String(err));
      setLiveStatusMessage('运行失败');
    } finally {
      setLiveLoading(false);
    }
  };

  // ===== 导出 Final Package JSON =====
  const exportPackage = () => {
    // Re8.1 WP5: prefer live result (real API), fallback to fixture
    const pkg = liveResult || result;
    if (!pkg) return;
    const payload = {
      case_key: pkg.case_key,
      topic: pkg.topic,
      mode: pkg.mode,
      fused_verdict: pkg.fused_verdict,
      fused_verdict_rationale: pkg.fused_verdict_rationale,
      final_research_package_sections: pkg.final_research_package_sections,
      seed_cards: pkg.seed_cards,
      gate_results: {
        seed_audit_gate: pkg.gate_seed_audit_gate,
        tailor_gate: pkg.gate_tailor_gate,
        final_review_gate: pkg.gate_final_review_gate,
      },
      tailored_method_summary: pkg.tailored_method_summary,
      hypothesis_preview: pkg.hypothesis_preview,
      n_ledger_entries: pkg.n_ledger_entries,
      gap_statuses: pkg.gap_statuses,
      exported_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `seeded_research_package_${pkg.case_key}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // ===== Re8.1 Task 16: 错误状态诚实展示 =====
  const ERROR_CATEGORY_LABELS: Record<string, string> = {
    'fused_blocked': 'Decision Fusion 阻断',
    'gate_unresolved:seed_audit_gate': '种子核验 Gate 未收敛（cap reached）',
    'gate_unresolved:tailor_gate': 'Tailor Gate 未收敛（cap reached）',
    'gate_unresolved:final_review_gate': '最终评审 Gate 未收敛（cap reached）',
    'seed_ambiguous': '种子身份歧义（ambiguous）',
    'seed_not_found': '种子未找到（not_found）',
    'network_offline': '网络离线模式',
  };

  const renderErrorCategories = (cats: string[]) => {
    if (!cats || cats.length === 0) return null;
    return (
      <div
        className="status-banner error"
        style={{ marginTop: '12px' }}
        data-testid="seeded-error-categories"
      >
        <span className="status-icon">⚠️</span>
        <div className="status-text">
          <div className="status-label">研究未通过 — 诚实错误展示</div>
          <div className="status-counts">
            {cats.map((c) => (
              <div key={c} style={{ fontSize: '13px', marginTop: '2px' }}>
                <span style={{ color: 'var(--color-error)', fontWeight: 600 }}>●</span>{' '}
                {ERROR_CATEGORY_LABELS[c] || c}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  // ===== Re8.1 Task 15.4: Gate repair 循环展示 =====
  const renderGateRounds = (gate: GateResult) => {
    if (!gate.all_rounds || gate.all_rounds.length === 0) return null;
    return (
      <div className="pa-small" style={{ marginTop: '6px' }} data-testid="gate-rounds-trajectory">
        <div className="pa-muted" style={{ marginBottom: '2px' }}>Round 轨迹：</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          {gate.all_rounds.map((r, i) => (
            <span
              key={i}
              className={`pa-gate-round-chip verdict-${r.verdict}`}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '4px',
                padding: '2px 8px', borderRadius: '10px',
                background: r.verdict === 'pass' ? '#dcfce7'
                  : r.verdict === 'revise' ? '#fef9c3'
                  : '#fee2e2',
                fontSize: '11px', fontWeight: 600,
              }}
              title={r.rationale}
            >
              <span>R{r.round_idx}</span>
              <span>{VERDICT_ICON[r.verdict] ?? '❓'}</span>
              <span style={{ color: '#64748b', fontWeight: 400 }}>{r.generated_by}</span>
            </span>
          ))}
        </div>
      </div>
    );
  };

  // ===== Re8.1 Task 16.5: 网络离线模式 banner =====
  const renderNetworkPolicyBanner = (data: SeededDemoResult) => {
    if ((data.network_policy || 'online') !== 'offline') return null;
    return (
      <div
        className="status-banner"
        style={{
          marginTop: '12px',
          background: '#fef3c7',
          border: '1px solid #fbbf24',
        }}
        data-testid="network-offline-banner"
      >
        <span className="status-icon">📵</span>
        <div className="status-text">
          <div className="status-label">网络离线模式已生效</div>
          <div className="status-counts">
            后端 NetworkPolicyGuard 已拦截所有外部 API 调用（Semantic Scholar / arXiv / GitHub / Crossref），仅使用本地缓存。
          </div>
        </div>
      </div>
    );
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
      {/* Re8.2 WP3: Seed Audit Gate structured diagnostics */}
      {gate.reason_code && (
        <div className="pa-small" style={{ marginTop: '6px' }} data-testid="seed-audit-reason-code">
          <span className="pa-muted">reason_code:</span>{' '}
          <code>{gate.reason_code}</code>
          {REASON_CODE_LABELS[gate.reason_code] && (
            <span className="pa-muted"> — {REASON_CODE_LABELS[gate.reason_code]}</span>
          )}
        </div>
      )}
      {(gate.seed_id ?? gate.candidate_count ?? gate.top_score ?? gate.repair_target) && (
        <div className="pa-small pa-muted" style={{ marginTop: '4px' }} data-testid="seed-audit-diagnostics">
          {gate.seed_id && <span>seed_id={gate.seed_id} · </span>}
          {typeof gate.candidate_count === 'number' && <span>candidates={gate.candidate_count} · </span>}
          {typeof gate.top_score === 'number' && <span>top_score={gate.top_score.toFixed(2)} · </span>}
          {gate.repair_target && <span>repair_target={gate.repair_target}</span>}
        </div>
      )}
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
      {/* Re8.1 Task 15.4: Gate repair 循环展示（round_idx + verdict 变化轨迹） */}
      {renderGateRounds(gate)}
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

      {/* ============ Section 3: 结果展示（Re8.1: 真实 API + fixture 并存） ============ */}
      <Card title="③ 结果展示（真实 API + fixture 联调）" testId="seeded-result-card">
        <div className="pa-interview-actions">
          <Button
            variant="primary"
            size="sm"
            onClick={runRealResearch}
            disabled={liveLoading}
            data-testid="seeded-run-real"
          >
            {liveLoading ? '运行中…' : '🚀 运行真实研究（Re8.1）'}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={loadFixture}
            disabled={loading || liveLoading}
            data-testid="seeded-load-fixture"
          >
            {loading ? '加载中…' : '加载 fixture（备用）'}
          </Button>
          {(liveResult || result) && (
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

        {/* Re8.1 WP5: live run status banner */}
        {liveStatus && (
          <div
            className={`status-banner ${liveStatus === 'error' ? 'error' : liveStatus === 'done' ? 'done' : ''}`}
            style={{ marginTop: '12px' }}
            data-testid="seeded-live-status"
          >
            <span className="status-icon">
              {liveStatus === 'done' ? '✅' : liveStatus === 'error' ? '❌' : '🔄'}
            </span>
            <div className="status-text">
              <div className="status-label">
                {liveStatus === 'submitting' && '提交中'}
                {liveStatus === 'running' && '后端运行中'}
                {liveStatus === 'fetching' && '拉取结果中'}
                {liveStatus === 'done' && '运行完成'}
                {liveStatus === 'error' && '运行失败'}
                {liveCaseId && ` · case_id=${liveCaseId}`}
              </div>
              <div className="status-counts">{liveStatusMessage}</div>
            </div>
          </div>
        )}

        {/* Re8.1 Task 16.1: 后端不可用 / 网络错误 — 诚实展示 */}
        {liveError && (
          <ErrorState
            title="真实后端调用失败"
            message={liveError}
            suggestion="请确认后端服务在 127.0.0.1:18181 运行（uvicorn apps.api.app.main:app），或检查 DEEPSEEK_API_KEY 等环境变量"
            onRetry={liveLoading ? undefined : runRealResearch}
          />
        )}

        {loadError && (
          <div className="status-banner error" style={{ marginTop: '12px' }}>
            <span className="status-icon">❌</span>
            <div className="status-text">
              <div className="status-label">fixture 加载失败</div>
              <div className="status-counts">{loadError}</div>
            </div>
          </div>
        )}

        {/* Re8.1 WP5: prefer liveResult (real API), fallback to fixture */}
        {(() => {
          const displayData = liveResult || result;
          if (!displayData) return null;
          return (
          <div className="pa-result-area" data-testid="seeded-result-area">
            {/* Re8.1 Task 16.5: 网络离线模式 banner */}
            {renderNetworkPolicyBanner(displayData)}

            {/* Re8.1 Task 16.2/16.3/16.4: 诚实错误分类展示 */}
            {displayData.error_categories && renderErrorCategories(displayData.error_categories)}

            {/* 三层 PASS 摘要 */}
            <div className="pa-pass-tiers" data-testid="pass-tiers">
              {renderPassTier('runtime_pass', displayData.runtime_pass)}
              {renderPassTier('contract_pass', displayData.contract_pass, displayData.contract_pass_reasons)}
              {renderPassTier('quality_pass', displayData.quality_pass, displayData.quality_pass_reasons)}
            </div>

            {/* 种子核验状态表 */}
            <details className="report-section" open>
              <summary>🌱 种子核验状态（{displayData.seed_cards.length}）</summary>
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
                    {displayData.seed_cards.map((c) => (
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
                    const gate = displayData[key] as GateResult;
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
                  style={{ color: FUSED_VERDICT_COLOR[displayData.fused_verdict] }}
                  data-testid="fused-verdict"
                >
                  {displayData.fused_verdict}
                </div>
                {displayData.fused_verdict_rationale && (
                  <div className="pa-muted" style={{ marginTop: '6px' }}>
                    {displayData.fused_verdict_rationale}
                  </div>
                )}
              </div>
            </details>

            {/* Evidence Gaps */}
            <details className="report-section">
              <summary>🔍 Evidence Gaps（{displayData.n_evidence_gaps ?? 0}）</summary>
              <div className="report-content">
                {displayData.gap_statuses && (
                  <div className="pa-small pa-muted" style={{ marginBottom: '8px' }}>
                    状态分布：{Object.entries(displayData.gap_statuses).map(([k, v]) => `${k}=${v}`).join(' · ')}
                  </div>
                )}
                <div className="pa-small pa-muted">
                  共 {displayData.n_evidence_gaps ?? 0} 个 gap（摘要未含逐条 gap 详情，详见完整 package）。
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
                      <td>{displayData.tailored_method_summary.core_method || '（空）'}</td>
                    </tr>
                    <tr>
                      <td><strong>contribution_type</strong></td>
                      <td>{displayData.tailored_method_summary.contribution_type ?? '（未设置）'}</td>
                    </tr>
                    <tr>
                      <td><strong>baseline_model</strong></td>
                      <td>{displayData.tailored_method_summary.baseline_model ?? '（未设置）'}</td>
                    </tr>
                    <tr>
                      <td><strong>tailored_verdict</strong></td>
                      <td>{displayData.tailored_verdict ?? '—'}</td>
                    </tr>
                    <tr>
                      <td><strong>ablation_rows</strong></td>
                      <td>{displayData.tailored_ablation_rows ?? 0}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </details>

            {/* Final Research Package 7 section 检查清单 */}
            <details className="report-section" open>
              <summary>📦 Final Research Package（{displayData.final_research_package_sections.length}/7 section）</summary>
              <div className="report-content">
                <ul className="pa-checklist">
                  {displayData.final_research_package_sections.map((sec) => (
                    <li key={sec} className="pa-checklist-item">
                      <span className="pa-pass-icon">✅</span>
                      <span>{sec}</span>
                    </li>
                  ))}
                  {(displayData.final_research_package_missing_sections ?? []).map((sec) => (
                    <li key={sec} className="pa-checklist-item">
                      <span className="pa-pass-icon">❌</span>
                      <span className="pa-muted">{sec}（缺失）</span>
                    </li>
                  ))}
                </ul>
                <div className="pa-small pa-muted" style={{ marginTop: '8px' }}>
                  ledger 条目：{displayData.n_ledger_entries ?? 0} · trace 事件：{displayData.n_trace_events ?? 0} · react actions：{displayData.n_react_actions ?? 0}
                </div>
              </div>
            </details>

            {/* 可证伪假设预览 */}
            {displayData.hypothesis_preview && (
              <details className="report-section">
                <summary>🧪 Falsifiable Hypothesis</summary>
                <div className="report-content">
                  <p className="pa-small">{displayData.hypothesis_preview}</p>
                </div>
              </details>
            )}

            {/* 运行元信息 */}
            <details className="report-section">
              <summary>📋 运行元信息</summary>
              <div className="report-content">
                <table className="snapshot-table">
                  <tbody>
                    <tr><td><strong>case_key</strong></td><td>{displayData.case_key}</td></tr>
                    {displayData.case_id && (
                      <tr><td><strong>case_id</strong></td><td>{displayData.case_id}</td></tr>
                    )}
                    <tr><td><strong>mode</strong></td><td>{displayData.mode}</td></tr>
                    <tr><td><strong>status</strong></td><td>{displayData.status}</td></tr>
                    <tr><td><strong>elapsed_s</strong></td><td>{displayData.elapsed_s}</td></tr>
                    <tr><td><strong>n_errors</strong></td><td>{displayData.n_errors ?? 0}</td></tr>
                    {displayData.error_samples && displayData.error_samples.length > 0 && (
                      <tr><td><strong>error_samples</strong></td><td>{displayData.error_samples.join(', ')}</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </details>
          </div>
          );
        })()}

        {!liveResult && !result && !loading && !liveLoading && !loadError && !liveError && (
          <div className="empty-state" style={{ padding: '24px' }}>
            <div className="empty-icon">📭</div>
            <div className="empty-title">尚未运行</div>
            <div className="empty-desc">
              点击「🚀 运行真实研究」调用真实后端 API（Re8.1 WP5），或「加载 fixture（备用）」查看静态产物。
              <br />
              支持 DOI / arXiv / URL / PDF / citation / title 六种输入形式。
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
