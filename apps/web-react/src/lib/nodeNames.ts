const NODE_NAMES: Record<string, string> = {
  intake: '接收题目',
  topic_parser: '关键词分解',
  search_planner: '搜索规划',
  search_agent: '多源检索',
  paper_retriever: '论文检索',
  quality_filter: '质量筛选',
  verify: '论文验证',
  quality_gate: '质量门',
  targeted_repair: '定向修复',
  citation_expander: '引用展开',
  dataset_repo_extractor: '数据集/仓库提取',
  dataset_repo: '数据集/仓库提取',
  evidence_graph_builder: '证据图谱构建',
  json_graph_builder: '证据图谱构建',
  evidence_auditor: '证据审计',
  baseline_classifier: '基线分类',
  feasibility_assessor: '可行性评估',
  human_gate_search: '补充搜索',
  work_package: '工作包生成',
  innovation_extractor: '创新点提取',
  sota_matcher: 'SOTA 对比',
  narrative_builder: '研究叙事生成',
  low_bar_review: '初审',
  optimization_advisor: '优化建议',
  devils_advocate_node: '反思审查',
  devils_advocate: '反思审查',
  human_gate: '人工审阅',
  final_recommendation: '最终推荐',
  review: '质量审核',
};

export function getNodeName(node: string): string {
  return NODE_NAMES[node] || node;
}

const NODE_GROUPS: Record<string, string> = {
  intake: 'input', topic_parser: 'parse',
  search_planner: 'parse', search_agent: 'search', paper_retriever: 'search',
  quality_filter: 'filter', verify: 'verify', quality_gate: 'verify',
  targeted_repair: 'repair', citation_expander: 'expand',
  dataset_repo_extractor: 'extract', dataset_repo: 'extract',
  evidence_graph_builder: 'extract', json_graph_builder: 'extract',
  evidence_auditor: 'audit', baseline_classifier: 'audit',
  feasibility_assessor: 'assess', human_gate_search: 'gate',
  work_package: 'gate', innovation_extractor: 'analyze',
  sota_matcher: 'analyze', narrative_builder: 'analyze',
  low_bar_review: 'review', optimization_advisor: 'review',
  devils_advocate_node: 'review', devils_advocate: 'review',
  human_gate: 'output', final_recommendation: 'output', review: 'output',
};

const GROUP_LABELS: Record<string, string> = {
  input: '输入', parse: '解析', search: '检索', filter: '筛选',
  verify: '验证', repair: '修复', expand: '展开', extract: '提取',
  audit: '审计', assess: '评估', gate: '决策', analyze: '分析',
  review: '审查', output: '输出',
};

const GROUP_ORDER = [
  'input', 'parse', 'search', 'filter', 'verify', 'repair',
  'expand', 'extract', 'audit', 'assess', 'gate', 'analyze',
  'review', 'output',
];

export function getGroup(node: string): string {
  return NODE_GROUPS[node] || 'unknown';
}

export function getGroupLabel(group: string): string {
  return GROUP_LABELS[group] || group;
}

export function getGroupOrder(): string[] {
  return GROUP_ORDER;
}
