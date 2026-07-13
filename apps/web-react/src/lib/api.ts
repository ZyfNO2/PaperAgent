const BASE = '/api/v1/research';

export async function submitTopic(topic: string): Promise<{ case_id: string; status: string }> {
  const resp = await fetch(BASE + '/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic }),
  });
  if (!resp.ok) throw new Error(`提交失败: ${resp.status}`);
  return resp.json();
}

export async function getCaseStatus(caseId: string) {
  const resp = await fetch(`${BASE}/${caseId}/status`);
  if (!resp.ok) throw new Error(`状态查询失败: ${resp.status}`);
  return resp.json();
}

export async function getCaseState(caseId: string) {
  const resp = await fetch(`${BASE}/${caseId}/state`);
  if (!resp.ok) throw new Error(`状态数据获取失败: ${resp.status}`);
  return resp.json();
}

export async function getCaseTrace(caseId: string) {
  const resp = await fetch(`${BASE}/${caseId}/trace`);
  if (!resp.ok) throw new Error(`轨迹数据获取失败: ${resp.status}`);
  return resp.json();
}

export async function getEvidenceGraph(caseId: string) {
  const resp = await fetch(`${BASE}/${caseId}/evidence-graph`);
  if (!resp.ok) throw new Error(`证据图谱获取失败: ${resp.status}`);
  return resp.json();
}

export async function listCases() {
  const resp = await fetch(BASE + '/');
  if (!resp.ok) throw new Error(`历史记录获取失败: ${resp.status}`);
  return resp.json();
}

export async function getHealthProviders() {
  const resp = await fetch(`${BASE}/health/providers`);
  if (!resp.ok) throw new Error(`健康检查失败: ${resp.status}`);
  return resp.json();
}

export async function getGraphTopology() {
  const resp = await fetch(`${BASE}/graph-topology`);
  if (!resp.ok) throw new Error(`拓扑图获取失败: ${resp.status}`);
  return resp.json();
}

// ===== Re8.1 WP5: Seeded Research real API =====

export interface SeededSubmission {
  topic: string;
  seeds: Array<{
    seed_id?: string;
    input_form: 'doi' | 'arxiv' | 'url' | 'pdf' | 'citation' | 'title';
    doi?: string;
    arxiv_id?: string;
    url?: string;
    title?: string;
    pdf_path?: string;
    authors?: string[];
    year?: number;
    role: string;
  }>;
  run_mode?: 'full_agent' | 'lite_chain' | 'offline_replay';
  network_policy?: 'online' | 'offline';
}

export interface SeededSubmissionResponse {
  case_id: string;
  status: string;
  n_seeds: number;
  run_mode: string;
  network_policy: string;
}

export async function submitSeededResearch(
  payload: SeededSubmission,
): Promise<SeededSubmissionResponse> {
  const resp = await fetch(BASE + '/seeded', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    // Surface server-side validation message when available
    let detail = '';
    try {
      const err = await resp.json();
      detail = err?.detail || '';
    } catch { /* ignore */ }
    throw new Error(`seeded 提交失败: ${resp.status}${detail ? ` — ${detail}` : ''}`);
  }
  return resp.json();
}

export async function getSeededSummary(caseId: string): Promise<Record<string, unknown>> {
  const resp = await fetch(`${BASE}/${caseId}/seeded-summary`);
  if (!resp.ok) {
    let detail = '';
    try {
      const err = await resp.json();
      detail = err?.detail || '';
    } catch { /* ignore */ }
    throw new Error(`seeded summary 获取失败: ${resp.status}${detail ? ` — ${detail}` : ''}`);
  }
  return resp.json();
}

/**
 * Poll case status until terminal (done/error) or timeout.
 * Returns the final status object. Throws on timeout.
 */
export async function pollCaseStatus(
  caseId: string,
  opts: {
    intervalMs?: number;
    timeoutMs?: number;
    onUpdate?: (status: Record<string, unknown>) => void;
  } = {},
): Promise<Record<string, unknown>> {
  const interval = opts.intervalMs ?? 2000;
  const timeout = opts.timeoutMs ?? 600_000; // 10 min default
  const start = Date.now();
  while (Date.now() - start < timeout) {
    let status: Record<string, unknown>;
    try {
      status = await getCaseStatus(caseId);
    } catch (e) {
      // Transient network error — keep polling
      await new Promise((r) => setTimeout(r, interval));
      continue;
    }
    opts.onUpdate?.(status);
    const s = String(status.status || 'unknown');
    if (s === 'done' || s === 'error') {
      return status;
    }
    await new Promise((r) => setTimeout(r, interval));
  }
  throw new Error(`轮询超时 (${timeout}ms)`);
}
