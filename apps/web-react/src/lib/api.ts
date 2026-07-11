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
