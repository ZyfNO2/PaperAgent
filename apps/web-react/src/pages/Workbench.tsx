import { useReducer, useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { connectSSE } from '../lib/sse';
import { getCaseStatus, getCaseState, submitTopic } from '../lib/api';
import { getNodeName, getGroup, getGroupLabel, getGroupOrder } from '../lib/nodeNames';
import { SourcePanel } from '../components/SourcePanel';
import { ErrorState } from '../components/ErrorState';
import { LoadingDots } from '../components/LoadingDots';
import { EmptyState } from '../components/EmptyState';
import { FeasibilityReport } from '../components/reports/FeasibilityReport';
import { ReviewReport } from '../components/reports/ReviewReport';
import { InnovationReport } from '../components/reports/InnovationReport';
import { NarrativeRevisions } from '../components/reports/NarrativeRevisions';
import { DagView } from '../components/reports/DagView';
import { BindingValidation } from '../components/reports/BindingValidation';
import { RagContextSection } from '../components/RagContextSection';
import type { Paper, RepoCandidate, DatasetCandidate, SSEEvent, CaseStatus, ResearchState } from '../types/api';

interface WorkbenchState {
  phase: 'idle' | 'searching' | 'filtering' | 'verifying' | 'expanding' | 'analyzing' | 'done' | 'error';
  currentNode: string | null;
  topic: string;
  papers: Paper[];
  repos: RepoCandidate[];
  datasets: DatasetCandidate[];
  counts: { papers: number; accept: number; weak: number; reject: number; expanded: number; surveys: number; repos: number; datasets: number };
  sources: Array<{ name: string; status: string; count: number }>;
  completedNodes: string[];
  elapsedTime: number;
  verifyRound: number;
  searchStep: number;
  error: { node: string; message: string } | null;
  caseId: string | null;
  finalState: ResearchState | null;
}

const initialState: WorkbenchState = {
  phase: 'idle',
  currentNode: null,
  topic: '',
  papers: [],
  repos: [],
  datasets: [],
  counts: { papers: 0, accept: 0, weak: 0, reject: 0, expanded: 0, surveys: 0, repos: 0, datasets: 0 },
  sources: [],
  completedNodes: [],
  elapsedTime: 0,
  verifyRound: 1,
  searchStep: 0,
  error: null,
  caseId: null,
  finalState: null,
};

type Action =
  | { type: 'SET_CASE_ID'; caseId: string }
  | { type: 'SSE_EVENT'; event: SSEEvent }
  | { type: 'SET_STATUS'; status: CaseStatus }
  | { type: 'SET_FINAL_STATE'; state: ResearchState }
  | { type: 'SET_ERROR'; error: { node: string; message: string } };

function reducer(state: WorkbenchState, action: Action): WorkbenchState {
  switch (action.type) {
    case 'SET_CASE_ID':
      return { ...initialState, caseId: action.caseId };

    case 'SET_ERROR':
      return { ...state, phase: 'error', error: action.error };

    case 'SET_STATUS':
      if (action.status.status === 'done' && state.phase !== 'done' && state.phase !== 'error') {
        return { ...state, phase: 'done', elapsedTime: action.status.elapsed_s || state.elapsedTime };
      }
      if (action.status.status === 'error' && state.phase !== 'error') {
        return { ...state, phase: 'error', error: { node: 'unknown', message: action.status.message || action.status.error || '运行出错' } };
      }
      if (action.status.current_node && action.status.status === 'running') {
        return { ...state, currentNode: action.status.current_node };
      }
      return state;

    case 'SET_FINAL_STATE':
      return { ...state, phase: 'done', finalState: action.state, elapsedTime: (action.state as Record<string, unknown>).elapsed_s as number || state.elapsedTime };

    case 'SSE_EVENT': {
      const ev = action.event;
      switch (ev.type) {
        case 'search_started':
          return { ...state, phase: 'searching', topic: (ev.data.topic as string) || state.topic };

        case 'node_current':
          return { ...state, currentNode: ev.data.node as string };

        case 'papers_update': {
          const papers = (ev.data.papers as Paper[]) || [];
          const repos = (ev.data.repos as RepoCandidate[]) || [];
          return {
            ...state,
            papers: papers.length > 0 ? papers : state.papers,
            repos: repos.length > 0 ? repos : state.repos,
            counts: { ...state.counts, papers: (ev.data.n_papers as number) || state.counts.papers, repos: (ev.data.n_repos as number) || state.counts.repos },
            searchStep: (ev.data.search_step as number) || state.searchStep,
          };
        }

        case 'papers_verified': {
          const papers = (ev.data.papers as Paper[]) || [];
          return {
            ...state,
            papers: papers.length > 0 ? papers : state.papers,
            counts: { ...state.counts, accept: (ev.data.n_verified as number) || 0, weak: (ev.data.n_weak as number) || 0 },
          };
        }

        case 'repos_update': {
          const repos = (ev.data.repos as RepoCandidate[]) || [];
          return { ...state, repos, counts: { ...state.counts, repos: (ev.data.n_repos as number) || 0 } };
        }

        case 'datasets_update': {
          const datasets = (ev.data.datasets as DatasetCandidate[]) || [];
          return { ...state, datasets, counts: { ...state.counts, datasets: (ev.data.n_datasets as number) || 0 } };
        }

        case 'adapter_result': {
          const name = ev.data.adapter as string;
          const count = (ev.data.count as number) || 0;
          const existing = state.sources.find((s) => s.name === name);
          let sources: WorkbenchState['sources'];
          if (existing) {
            sources = state.sources.map((s) => s.name === name ? { ...s, count: s.count + count, status: 'ok' } : s);
          } else {
            sources = [...state.sources, { name, count, status: 'ok' }];
          }
          return { ...state, sources };
        }

        case 'adapter_status': {
          const perAdapter = (ev.data.per_adapter as Record<string, number>) || {};
          const failed = (ev.data.failed_adapters as string[]) || [];
          const skipped = (ev.data.skipped_adapters as string[]) || [];
          const sources = Object.entries(perAdapter).map(([name, count]) => {
            let status = 'ok';
            if (failed.includes(name)) status = 'error';
            else if (skipped.includes(name)) status = 'skipped';
            else if (count === 0) status = 'empty';
            return { name, count, status };
          });
          for (const name of skipped) {
            if (!sources.find((s) => s.name === name)) {
              sources.push({ name, count: 0, status: 'skipped' });
            }
          }
          return { ...state, sources };
        }

        case 'search_completed':
          return { ...state, phase: 'filtering' };

        case 'filter_result':
          return { ...state, phase: 'verifying', counts: { ...state.counts, papers: (ev.data.kept as number) || 0 } };

        case 'verify_completed': {
          const round = (ev.data.round as number) || state.verifyRound;
          const counts = {
            ...state.counts,
            accept: (ev.data.accepted as number) || 0,
            weak: (ev.data.weak_reject as number) || 0,
            reject: (ev.data.rejected as number) || 0,
          };
          return { ...state, phase: round > 1 ? 'expanding' : 'verifying', verifyRound: round, counts };
        }

        case 'candidate_count': {
          const data = ev.data;
          const counts = { ...state.counts };
          if ('papers' in data) counts.papers = (data.papers as number) || counts.papers;
          if ('accept' in data) counts.accept = (data.accept as number) || counts.accept;
          if ('weak' in data) counts.weak = (data.weak as number) || counts.weak;
          if ('reject' in data) counts.reject = (data.reject as number) || counts.reject;
          if ('expanded' in data) counts.expanded = (data.expanded as number) || counts.expanded;
          if ('surveys' in data) counts.surveys = (data.surveys as number) || counts.surveys;
          if ('repos' in data) counts.repos = (data.repos as number) || counts.repos;
          if ('datasets' in data) counts.datasets = (data.datasets as number) || counts.datasets;
          return { ...state, counts };
        }

        case 'expansion_started':
          return { ...state, phase: 'expanding' };

        case 'expansion_completed':
          return { ...state, counts: { ...state.counts, expanded: (ev.data.total_expanded as number) || 0 } };

        case 'node_complete':
          if (!state.completedNodes.includes(ev.data.node as string)) {
            return { ...state, completedNodes: [...state.completedNodes, ev.data.node as string] };
          }
          return state;

        case 'done':
          return { ...state, phase: 'done', elapsedTime: (ev.data.total_elapsed_s as number) || state.elapsedTime };

        case 'error':
          return { ...state, phase: 'error', error: { node: (ev.data.node as string) || 'unknown', message: (ev.data.message as string) || '未知错误' } };

        default:
          return state;
      }
    }
    default:
      return state;
  }
}

function getHumanStatus(state: WorkbenchState): string {
  if (state.error) return `出错了：${state.error.message}`;
  switch (state.phase) {
    case 'searching': return `正在检索论文（第 ${state.searchStep || 1} 轮）· 已找到 ${state.papers.length} 篇`;
    case 'filtering': return `正在筛选 ${state.counts.papers || state.papers.length} 篇候选论文`;
    case 'verifying': return `正在验证论文质量（第 ${state.verifyRound} 轮）· 已验证 ${state.counts.accept + state.counts.weak} 篇`;
    case 'expanding': return `正在展开引用网络（${state.counts.expanded} 篇）`;
    case 'analyzing': return '正在分析可行性和创新点';
    case 'done': return `研究完成，用时 ${state.elapsedTime.toFixed(0)} 秒`;
    default: return '准备中...';
  }
}

const REPORT_SECTIONS = [
  { key: 'feasibility_report', title: '可行性评估', icon: '📊' },
  { key: 'review_report', title: '最终审核', icon: '✅' },
  { key: 'work_packages', title: '工作包', icon: '📦' },
  { key: 'research_narrative', title: '研究叙事', icon: '📝' },
  { key: 'innovation_points', title: '创新点', icon: '💡' },
  { key: 'optimization_directions', title: '优化方向', icon: '🔧' },
  { key: 'sota_comparison', title: 'SOTA 对比', icon: '🏆' },
  { key: 'evidence_graph', title: '证据图谱', icon: '🔗' },
  { key: 'trace_events', title: '执行轨迹', icon: '📋' },
];

const VERDICT_ICONS: Record<string, string> = {
  accept: '✅',
  weak_reject: '⚠️',
  reject: '❌',
};

export function Workbench() {
  const { caseId: urlCaseId } = useParams();
  const navigate = useNavigate();
  const [state, dispatch] = useReducer(reducer, initialState);
  const [loadingState, setLoadingState] = useState(true);

  const loadFinalState = useCallback(async (cid: string) => {
    try {
      const finalState = await getCaseState(cid);
      dispatch({ type: 'SET_FINAL_STATE', state: finalState });
    } catch {
      // ignore — SSE done event already set phase
    }
  }, []);

  useEffect(() => {
    if (!urlCaseId) {
      setLoadingState(false);
      return;
    }

    dispatch({ type: 'SET_CASE_ID', caseId: urlCaseId });
    setLoadingState(true);

    // First check if case is already done
    getCaseStatus(urlCaseId)
      .then((status: CaseStatus) => {
        dispatch({ type: 'SET_STATUS', status });
        if (status.status === 'done') {
          loadFinalState(urlCaseId);
          setLoadingState(false);
        } else if (status.status === 'error') {
          dispatch({ type: 'SET_ERROR', error: { node: 'unknown', message: status.message || '运行出错' } });
          setLoadingState(false);
        } else if (status.status === 'running') {
          setLoadingState(false);
        } else {
          setLoadingState(false);
        }
      })
      .catch(() => setLoadingState(false));

    // Connect SSE for running cases
    let disconnect: (() => void) | null = null;
    if (urlCaseId && !urlCaseId.includes('..') && !urlCaseId.includes('/')) {
      disconnect = connectSSE(urlCaseId, {
        onEvent: (event) => {
          dispatch({ type: 'SSE_EVENT', event });
          if (event.type === 'done') {
            loadFinalState(urlCaseId);
          }
        },
        onError: () => {
          // Re-check status on SSE disconnect
          getCaseStatus(urlCaseId).then((status) => {
            dispatch({ type: 'SET_STATUS', status });
            if (status.status === 'done') loadFinalState(urlCaseId);
          }).catch(() => {});
        },
      });
    }

    return () => {
      disconnect?.();
    };
  }, [urlCaseId, loadFinalState]);

  if (!urlCaseId) {
    return (
      <EmptyState
        icon="🔬"
        title="工作台"
        description="从首页提交题目，或在历史记录中选择一个 case 来查看工作台"
        action={{ label: '去首页', onClick: () => navigate('/') }}
      />
    );
  }

  if (loadingState) {
    return <div style={{ textAlign: 'center', padding: '48px' }}><LoadingDots text="正在加载" /></div>;
  }

  // Progress bar
  const groups = getGroupOrder();
  const completedGroups = new Set(state.completedNodes.map(getGroup));
  const currentGroup = state.currentNode ? getGroup(state.currentNode) : null;
  const progressPercent = state.phase === 'done' ? 100 :
    Math.round((completedGroups.size / groups.length) * 100);

  const statusIcon = state.phase === 'done' ? '✅' : state.phase === 'error' ? '❌' : '🔄';
  const statusClass = state.phase === 'done' ? 'done' : state.phase === 'error' ? 'error' : '';

  return (
    <div>
      <div className="workbench-header">
        <div>
          <div className="workbench-topic">{state.topic || state.finalState?.topic || urlCaseId}</div>
          <div className="workbench-meta">
            <span>Case ID: {urlCaseId}</span>
            {state.elapsedTime > 0 && <span>⏱ 已运行 {state.elapsedTime.toFixed(0)}s</span>}
          </div>
        </div>
        <button className="btn-secondary" onClick={() => navigate('/')}>← 返回首页</button>
      </div>

      {/* Progress bar */}
      <div className="progress-bar-container">
        <div className="progress-steps">
          {groups.map((g) => (
            <span
              key={g}
              className={`progress-step ${currentGroup === g ? 'active' : ''} ${completedGroups.has(g) ? 'done' : ''}`}
            >
              {getGroupLabel(g)}
            </span>
          ))}
        </div>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${progressPercent}%` }}></div>
        </div>
      </div>

      {/* Status banner */}
      <div className={`status-banner ${statusClass}`}>
        <span className="status-icon">{statusIcon}</span>
        <div className="status-text">
          <div className="status-label">{getHumanStatus(state)}</div>
          {(state.counts.papers > 0 || state.counts.repos > 0) && (
            <div className="status-counts">
              已收集：{state.counts.accept + state.counts.weak || state.papers.length} 篇论文 · {state.counts.repos || state.repos.length} 个仓库 · {state.counts.datasets || state.datasets.length} 个数据集
            </div>
          )}
        </div>
      </div>

      {/* Current node */}
      {state.currentNode && state.phase !== 'done' && state.phase !== 'error' && (
        <div style={{ padding: '8px 16px', fontSize: '14px', color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
          当前步骤：<strong>{getNodeName(state.currentNode)}</strong>
        </div>
      )}

      {/* Source panel */}
      <SourcePanel sources={state.sources} />

      {/* Paper list */}
      {state.papers.length > 0 && (
        <div className="paper-list">
          <h3>论文列表（{state.papers.length}）</h3>
          {state.papers.slice(0, 50).map((p, i) => (
            <div key={i} className="paper-item">
              <span className="paper-verdict">
                {p.verdict ? VERDICT_ICONS[p.verdict] || '📄' : '🔍'}
              </span>
              <div className="paper-info">
                <div className="paper-title">{p.title}</div>
                <div className="paper-meta">
                  {p.source && <span>{p.source} </span>}
                  {p.year && <span>· {p.year} </span>}
                  {p.relation_to_topic && <span>· {p.relation_to_topic}</span>}
                </div>
              </div>
            </div>
          ))}
          {state.papers.length > 50 && (
            <div style={{ padding: '8px', textAlign: 'center', fontSize: '13px', color: 'var(--color-text-secondary)' }}>
              显示前 50 条，共 {state.papers.length} 条
            </div>
          )}
        </div>
      )}

      {/* Repo list */}
      {state.repos.length > 0 && (
        <div className="paper-list">
          <h3>仓库列表（{state.repos.length}）</h3>
          {state.repos.slice(0, 30).map((r, i) => (
            <div key={i} className="paper-item">
              <span className="paper-verdict">📦</span>
              <div className="paper-info">
                <div className="paper-title">{r.full_name || r.url}</div>
                <div className="paper-meta">
                  {r.language && <span>{r.language} </span>}
                  {r.stars != null && <span>· ⭐ {r.stars} </span>}
                  {r.description && <span>· {r.description}</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Dataset list */}
      {state.datasets.length > 0 && (
        <div className="paper-list">
          <h3>数据集列表（{state.datasets.length}）</h3>
          {state.datasets.slice(0, 30).map((d, i) => (
            <div key={i} className="paper-item">
              <span className="paper-verdict">📊</span>
              <div className="paper-info">
                <div className="paper-title">{d.name}</div>
                <div className="paper-meta">
                  {d.source && <span>{d.source} </span>}
                  {d.description && <span>· {d.description}</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Report sections */}
      {state.finalState && (() => {
        const fs = state.finalState as Record<string, any>;
        const sections: JSX.Element[] = [];

        // Feasibility
        if (fs.feasibility_report) {
          sections.push(
            <details key="feasibility" className="report-section" open>
              <summary>📊 可行性评估</summary>
              <div className="report-content"><FeasibilityReport data={fs.feasibility_report} /></div>
            </details>
          );
        }

        // Review
        if (fs.review_report) {
          sections.push(
            <details key="review" className="report-section" open>
              <summary>✅ 最终审核</summary>
              <div className="report-content"><ReviewReport data={fs.review_report} /></div>
            </details>
          );
        }

        // Work packages + DAG
        if (fs.work_packages && fs.work_packages.length > 0) {
          const dag = fs.low_bar_review?.dag;
          sections.push(
            <details key="wp" className="report-section" open>
              <summary>📦 工作包（{fs.work_packages.length}）</summary>
              <div className="report-content">
                {dag && <DagView dag={dag} />}
                <div style={{ marginTop: '12px' }}>
                  {fs.work_packages.map((wp: any, i: number) => (
                    <div key={i} style={{ marginBottom: '8px', padding: '8px', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
                      <strong>{wp.title}</strong>
                      {wp.objective && <p style={{ fontSize: '13px', color: '#64748b' }}>{wp.objective}</p>}
                      {wp.method && <p style={{ fontSize: '12px' }}>方法: {wp.method}</p>}
                      {wp.deliverable && <p style={{ fontSize: '12px' }}>产出: {wp.deliverable}</p>}
                      {wp.effort && <span style={{ fontSize: '11px', color: '#94a3b8' }}>工作量: {wp.effort}</span>}
                    </div>
                  ))}
                </div>
              </div>
            </details>
          );
        }

        // Innovation
        if (fs.innovation_points && fs.innovation_points.length > 0) {
          sections.push(
            <details key="innovation" className="report-section">
              <summary>💡 创新点（{fs.innovation_points.length}）</summary>
              <div className="report-content"><InnovationReport data={{ innovation_points: fs.innovation_points }} /></div>
            </details>
          );
        }

        // Narrative + revisions
        if (fs.research_narrative || fs.narrative_revisions) {
          sections.push(
            <details key="narrative" className="report-section">
              <summary>📝 研究叙事</summary>
              <div className="report-content">
                {fs.research_narrative?.nick_model_name && (
                  <div style={{ fontWeight: 600, fontSize: '15px', marginBottom: '8px' }}>{fs.research_narrative.nick_model_name}</div>
                )}
                {fs.research_narrative?.narrative_summary && (
                  <p style={{ fontSize: '14px', marginBottom: '12px' }}>{fs.research_narrative.narrative_summary}</p>
                )}
                {fs.narrative_revisions && fs.narrative_revisions.length > 0 && (
                  <div>
                    <h4>修订历史</h4>
                    <NarrativeRevisions revisions={fs.narrative_revisions} />
                  </div>
                )}
              </div>
            </details>
          );
        }

        // Binding validation
        if (fs.low_bar_review?.binding_validation) {
          sections.push(
            <details key="binding" className="report-section">
              <summary>🔍 证据链验证</summary>
              <div className="report-content"><BindingValidation data={fs.low_bar_review.binding_validation} /></div>
            </details>
          );
        }

        // Remaining sections as JSON fallback
        const remaining = [
          { key: 'optimization_directions', title: '优化方向', icon: '🔧' },
          { key: 'sota_comparison', title: 'SOTA 对比', icon: '🏆' },
          { key: 'evidence_graph', title: '证据图谱', icon: '🔗' },
          { key: 'trace_events', title: '执行轨迹', icon: '📋' },
        ];
        for (const sec of remaining) {
          const data = fs[sec.key];
          if (data && !(Array.isArray(data) && data.length === 0)) {
            sections.push(
              <details key={sec.key} className="report-section">
                <summary>{sec.icon} {sec.title}</summary>
                <div className="report-content"><pre>{JSON.stringify(data, null, 2)}</pre></div>
              </details>
            );
          }
        }

        // RAG context section (when done)
        if (state.phase === 'done' && state.caseId) {
          sections.push(<RagContextSection key="rag" caseId={state.caseId} />);
        }

        return <div>{sections}</div>;
      })()}

      {/* Error state */}
      {state.phase === 'error' && state.error && (
        <ErrorState
          title="研究过程出错"
          message={`${state.error.node}: ${state.error.message}`}
          suggestion="可能是 LLM 或外部 API 暂时不可用，请检查后端日志或稍后重试"
          onRetry={() => {
            if (state.topic) {
              submitTopic(state.topic).then((result) => {
                navigate(`/workbench/${result.case_id}`);
              }).catch(() => navigate('/'));
            } else {
              navigate('/');
            }
          }}
        />
      )}
    </div>
  );
}
