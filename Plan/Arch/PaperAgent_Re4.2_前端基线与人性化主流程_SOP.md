# PaperAgent Re4.2：前端基线、Vite 与人性化主流程 SOP

> **承接**：Re4.1 工程控制面已完成（Gate A 全通过，端到端 case re41-verify-001 跑通）。
>
> **本 SOP 覆盖 Day 2 全部任务**：新建 `apps/web-react/` 最小 React + Vite shell，
> 实现首页 + 工作台 + RAG 占位路由，人性化状态/错误/空状态，Playwright 截图基线。
>
> **预计时长**：6–8 小时，分 7 个 Phase。
> **参考项目复用**：academic-research-skills (CC BY-NC) `progress_dashboard_template.md` / `pipeline_state_machine.md` 行为级借鉴 (B 级)；
> AutoResearchClaw (MIT) SSE 事件分层思想 (B 级)。不复制代码。

---

## 0. 当前事实基线（已验证）

| 项 | 现状 | Day 2 决策 |
|---|---|---|
| `apps/web-react/` | **不存在** | 新建最小 Vite shell |
| `apps/web/index.html` | 单文件 vanilla JS (~35KB)，含全部 CSS+HTML+JS | 保留不动，作为回滚 |
| 前端服务方式 | FastAPI StaticFiles 挂载 `/web`，端口 18181 | 不变；新 Vite dev server 独立端口 18183，proxy `/api` → 18181 |
| Node/npm 工具链 | 项目中不存在 | 在 `apps/web-react/` 内独立 `package.json`，不影响 Python 依赖 |
| 迁移矩阵 | 标记 Sessions 52–56 "done"，实际全部未完成 | 已在 Re4.1 顶部声明；本 SOP 覆盖实际落地 |
| Playwright e2e | `apps/web/e2e/test_re2_4_frontend.py` 活跃（15 tests，端口 18181 `/web/`） | 保留为旧前端回归；新建 `apps/web-react/e2e/` |
| SSE 事件 | 13 种事件类型已实现（详见 API 契约） | React 前端完整复现 |
| API 端点 | 18+ 端点，详见 Re4.1 验证 | React 前端调用同一套 API |
| SourcePolicy | `summary()` 返回 per-source enabled/status/concurrency | 前端需展示来源状态 |
| case_id | 服务端 UUID 或受限 slug | 前端不传 case_id，由服务端生成 |

### API 契约摘要（前端必须消费）

**REST 端点**：

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/v1/research/` | 提交题目（body: `{topic, case_id?}`，返回 `{case_id, status}`） |
| GET | `/api/v1/research/` | 列出历史 case |
| GET | `/api/v1/research/{case_id}/status` | 轮询状态 |
| GET | `/api/v1/research/{case_id}/stream` | SSE 实时进度 |
| GET | `/api/v1/research/{case_id}/state` | 完整 ResearchState |
| GET | `/api/v1/research/{case_id}/trace` | trace 事件列表 |
| GET | `/api/v1/research/{case_id}/timeline` | 带累计计数的 timeline |
| GET | `/api/v1/research/{case_id}/evidence-graph` | 证据图谱 JSON |
| GET | `/api/v1/research/{case_id}/feasibility` | 可行性报告 |
| GET | `/api/v1/research/{case_id}/review` | 最终审核报告 |
| GET | `/api/v1/research/{case_id}/innovation` | 创新点 |
| GET | `/api/v1/research/{case_id}/narrative` | 研究叙事 |
| GET | `/api/v1/research/{case_id}/optimization` | 优化方向 |
| GET | `/api/v1/research/{case_id}/sota` | SOTA 对比 |
| GET | `/api/v1/research/graph-topology` | 24 节点静态拓扑 |
| GET | `/api/v1/research/health/providers` | 6-provider 健康检查 |

**SSE 事件类型**：

| 事件 | data 关键字段 | 前端展示 |
|---|---|---|
| `search_started` | `case_id, status` | 状态：检索已启动 |
| `node_current` | `node` | 当前节点高亮 + 人话翻译 |
| `papers_update` | `papers[], n_papers, n_repos, search_step` | 论文卡片实时追加 |
| `adapter_result` | `adapter, count` | 来源计数更新 |
| `adapter_status` | `per_adapter, failed_adapters, skipped_adapters, total_raw` | 来源面板：成功/失败/跳过 |
| `search_completed` | `total_raw` | 检索完成，进入筛选 |
| `filter_result` | `kept, dropped, llm_judged` | 筛选结果计数 |
| `verify_completed` | `accepted, weak_reject, rejected, round` | 验证结果分布 |
| `candidate_count` | `papers, accept, weak, reject` 或 `expanded, surveys, repos, seeds` | 候选数量面板 |
| `expansion_started` | `n_seeds, seed_titles[], seed_scores[]` | 引用展开进度 |
| `expansion_completed` | `total_expanded, n_surveys, n_repos` | 展开完成 |
| `node_complete` | `node, output, elapsed_s` | 节点完成（通用） |
| `done` | `case_id, total_elapsed_s, n_verified, n_work_packages, n_baseline` | 全部完成 |
| `error` | `node, message` | 错误提示 + 建议动作 |

### 参考项目可用资产

| 源 | 文件 | 复用级别 | Day 2 用途 |
|---|---|---|---|
| academic-research-skills (CC BY-NC) | `progress_dashboard_template.md` | B | 阶段状态可视化思想：`pending → in_progress → completed → skipped → blocked` |
| academic-research-skills (CC BY-NC) | `pipeline_state_machine.md` | B | 状态机转换定义；Re4.1 已实现 StageContract，前端可消费 |
| academic-research-skills (CC BY-NC) | `score_trajectory_protocol.md` | B | 分数趋势展示思想（后续 Day 3/7） |
| AutoResearchClaw (MIT) | SSE 事件分层（无前端代码） | B | 事件优先级：error > node_current > papers_update > count > node_complete |

> **许可证行动**：Day 2 不复制外部代码。前端从零编写，仅借鉴状态展示和事件分层思想。

---

## 1. 本轮目标

### 核心交付

1. **`apps/web-react/`** 最小 React + Vite + TypeScript shell，dev port 18183
2. **首页**：价值主张、三步引导、两个 Demo Case 入口
3. **工作台**：题目输入、SSE 实时进度、论文列表、来源状态、最终报告折叠区
4. **RAG 占位路由**：仅页面框架 + "Re4.5 上线" 提示
5. **统一交互**：空状态、错误说明 + 建议动作、加载语义、键盘可达性
6. **Playwright 截图基线**：home、workbench、失败状态、报告页

### 人性化设计原则

- 不展示 Agent 内部术语（如 `devils_advocate_node`），用人话翻译
- 任何 API 错误有中文解释和建议动作
- 空状态有引导文案和 CTA 按钮
- Human Gate 仅作为"审阅提示"，不阻塞流程

### 不做

- 不删除或修改 `apps/web/index.html`（保留回滚）
- 不修改后端 API 或 graph 拓扑
- 不实现 RAG 问答功能（Day 5–6）
- 不实现完整论文编辑器（Day 3）
- 不做复杂动画或完整 design system（MVP 边界）

> **强制规则**：每个 Phase 完成后必须跑 `pytest --collect-only` 确认零 error；
> 全部 Phase 完成后必须跑一个端到端 case 验证产物完整性和正确性（见 Phase 7）。

---

## 2. Phase 设计

### Phase 1：Vite 项目脚手架 — 1h

#### Fix 1.1: 创建 `apps/web-react/`

**目录结构**：
```
apps/web-react/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── router.tsx
│   ├── types/
│   │   └── api.ts              # API 响应类型定义
│   ├── lib/
│   │   ├── api.ts              # fetch 封装
│   │   ├── sse.ts              # SSE EventSource 封装
│   │   └── nodeNames.ts        # 节点内部名 → 人话映射
│   ├── components/
│   │   ├── Layout.tsx          # 公共布局（导航栏 + 内容区）
│   │   ├── EmptyState.tsx      # 统一空状态
│   │   ├── ErrorState.tsx      # 统一错误状态 + 建议动作
│   │   ├── LoadingDots.tsx     # 统一加载语义
│   │   └── SourcePanel.tsx      # 来源状态面板
│   ├── pages/
│   │   ├── Home.tsx            # 首页
│   │   ├── Workbench.tsx       # 工作台
│   │   └── RagPlaceholder.tsx  # RAG 占位
│   └── styles/
│       └── global.css          # 全局样式（含 CSS 变量）
└── e2e/
    └── test_re42_react_web.py   # Playwright 截图基线
```

**`package.json`**：
```json
{
  "name": "paperagent-web",
  "private": true,
  "version": "0.4.0-dev",
  "type": "module",
  "scripts": {
    "dev": "vite --port 18183 --host 127.0.0.1",
    "build": "tsc && vite build",
    "preview": "vite preview --port 18183"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.26.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0"
  }
}
```

**`vite.config.ts`**：
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 18183,
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:18181',
        changeOrigin: true,
      },
    },
  },
})
```

**`tsconfig.json`**：
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

#### Fix 1.2: 安装依赖

```bash
cd apps/web-react
npm install
```

#### Fix 1.3: 验证 Vite 启动

```bash
npm run dev
# 预期：http://127.0.0.1:18183 可访问，显示 React 默认页面
```

#### Fix 1.4: `.gitignore` 更新

**文件**：`G:\PaperAgent\.gitignore`

追加：
```
# Vite
apps/web-react/node_modules/
apps/web-react/dist/
```

---

### Phase 2：类型定义 + API 封装 — 1h

#### Fix 2.1: API 类型定义

**文件**：`apps/web-react/src/types/api.ts`

```typescript
// ===== Research State =====
export interface ResearchState {
  case_id: string;
  topic: string;
  topic_atoms?: TopicAtoms;
  verified_papers?: Paper[];
  repo_candidates?: RepoCandidate[];
  dataset_candidates?: DatasetCandidate[];
  feasibility_report?: FeasibilityReport;
  review_report?: ReviewReport;
  innovation_points?: InnovationPoint[];
  research_narrative?: ResearchNarrative;
  optimization_directions?: OptimizationDirection[];
  work_packages?: WorkPackage[];
  evidence_graph?: EvidenceGraph;
  source_ledger?: SourceLedgerRecord[];
  trace_events?: TraceEvent[];
  // ... 其余字段为 optional
}

export interface TopicAtoms {
  method?: string[];
  task?: string[];
  object?: string[];
  domain?: string;
}

export interface Paper {
  title: string;
  authors?: string[];
  year?: number | null;
  doi?: string;
  arxiv_id?: string;
  url?: string;
  abstract?: string;
  source?: string;
  verification_verdict?: 'accept' | 'weak_reject' | 'reject';
  hit_keywords?: string[];
  citation_count?: number;
  relation_to_topic?: string;
}

export interface RepoCandidate {
  full_name: string;
  url: string;
  stars?: number;
  description?: string;
  language?: string;
}

export interface DatasetCandidate {
  name: string;
  url?: string;
  source?: string;
  description?: string;
}

export interface FeasibilityReport {
  score: number;
  verdict: 'recommended' | 'risky' | 'not_recommended';
  reasoning?: string;
  strengths?: string[];
  risks?: string[];
}

export interface ReviewReport {
  review_status: 'ACCEPT' | 'MINOR_REVISION' | 'BLOCK';
  dimensions?: Record<string, number>;
  fabrication_alerts?: string[];
  risks?: string[];
}

export interface InnovationPoint {
  title: string;
  description: string;
  // Re4.3 将扩展: candidate_ids, evidence_snippets, scores
}

export interface ResearchNarrative {
  three_problems?: string[];
  nick_model_name?: string;
  abstract_draft?: string;
  chapter_outline?: string[];
}

export interface OptimizationDirection {
  direction: string;
  rationale?: string;
}

export interface WorkPackage {
  title: string;
  description?: string;
  // Re4.3 将扩展: objective, method, deliverable, effort, risk, prerequisite_ids
}

export interface EvidenceGraph {
  nodes: EvidenceNode[];
  edges: EvidenceEdge[];
}

export interface EvidenceNode {
  id: string;
  type: string;
  label: string;
}

export interface EvidenceEdge {
  from: string;
  to: string;
  label?: string;
}

// ===== SSE Events =====
export type SSEEvent =
  | { type: 'search_started'; data: { case_id: string; status: string } }
  | { type: 'node_current'; data: { node: string } }
  | { type: 'papers_update'; data: { papers: Paper[]; n_papers: number; n_repos: number; search_step: number } }
  | { type: 'adapter_result'; data: { adapter: string; count: number } }
  | { type: 'adapter_status'; data: { per_adapter: Record<string, number>; failed_adapters: string[]; skipped_adapters: string[]; total_raw: number } }
  | { type: 'search_completed'; data: { total_raw: number } }
  | { type: 'filter_result'; data: { kept: number; dropped: number; llm_judged: number } }
  | { type: 'verify_completed'; data: { accepted: number; weak_reject: number; rejected: number; round: number } }
  | { type: 'candidate_count'; data: Record<string, number> }
  | { type: 'expansion_started'; data: { n_seeds: number; seed_titles: string[]; seed_scores: number[] } }
  | { type: 'expansion_completed'; data: { total_expanded: number; n_surveys: number; n_repos: number } }
  | { type: 'node_complete'; data: { node: string; output: Record<string, unknown>; elapsed_s: number } }
  | { type: 'done'; data: { case_id: string; total_elapsed_s: number; total_events: number; n_verified: number; n_work_packages: number; n_baseline: number } }
  | { type: 'error'; data: { node: string; message: string } };

// ===== SourcePolicy =====
export interface SourcePolicyEntry {
  enabled: boolean;
  status: 'enabled' | 'skipped' | 'rate_limited' | 'failed';
  concurrency: number;
  retries: number;
  timeout: number;
}

// ===== Trace =====
export interface TraceEvent {
  node: string;
  started_at: string;
  ended_at: string;
  elapsed_s: number;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  tool_calls: unknown[];
  errors: string[];
  state_keys: string[];
  provider?: string;
}

// ===== Case Status =====
export interface CaseStatus {
  status: 'running' | 'done' | 'error' | 'unknown';
  current_node?: string;
  n_trace_events?: number;
  elapsed_s?: number;
  n_papers?: number;
  n_packages?: number;
  error?: string;
  has_state_json: boolean;
  has_trace_json: boolean;
  has_evidence_graph_json: boolean;
}

export interface CaseListItem {
  case_id: string;
  file_size: number;
  mtime: number;
  status: string;
}
```

#### Fix 2.2: fetch 封装

**文件**：`apps/web-react/src/lib/api.ts`

```typescript
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
```

#### Fix 2.3: SSE 封装

**文件**：`apps/web-react/src/lib/sse.ts`

```typescript
import type { SSEEvent } from '../types/api';

export function connectSSE(
  caseId: string,
  handlers: {
    onEvent: (event: SSEEvent) => void;
    onError?: (error: Event) => void;
  }
): () => void {
  const source = new EventSource(`/api/v1/research/${caseId}/stream`);

  const eventTypes = [
    'search_started', 'node_current', 'papers_update', 'adapter_result',
    'adapter_status', 'search_completed', 'filter_result', 'verify_completed',
    'candidate_count', 'expansion_started', 'expansion_completed',
    'node_complete', 'done', 'error',
  ];

  const cleanups: (() => void)[] = [];

  for (const type of eventTypes) {
    const listener = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        handlers.onEvent({ type: type as SSEEvent['type'], data });
      } catch {
        // 忽略解析失败
      }
    };
    source.addEventListener(type, listener);
    cleanups.push(() => source.removeEventListener(type, listener));
  }

  source.onerror = (e) => {
    handlers.onError?.(e);
    source.close();
  };

  return () => {
    cleanups.forEach(fn => fn());
    source.close();
  };
}
```

#### Fix 2.4: 节点名称人话映射

**文件**：`apps/web-react/src/lib/nodeNames.ts`

```typescript
// 节点内部名 → 人话描述
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
  evidence_graph_builder: '证据图谱构建',
  json_graph_builder: '证据图谱构建',
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
  human_gate: '人工审阅',
  final_recommendation: '最终推荐',
  review: '质量审核',
};

export function getNodeName(node: string): string {
  return NODE_NAMES[node] || node;
}

// 阶段分组（用于进度条着色）
const NODE_GROUPS: Record<string, string> = {
  intake: 'input', topic_parser: 'parse',
  search_planner: 'parse', search_agent: 'search', paper_retriever: 'search',
  quality_filter: 'filter', verify: 'verify', quality_gate: 'verify',
  targeted_repair: 'repair', citation_expander: 'expand',
  dataset_repo_extractor: 'extract', evidence_graph_builder: 'extract',
  json_graph_builder: 'extract', baseline_classifier: 'audit',
  feasibility_assessor: 'assess', human_gate_search: 'gate',
  work_package: 'gate', innovation_extractor: 'analyze',
  sota_matcher: 'analyze', narrative_builder: 'analyze',
  low_bar_review: 'review', optimization_advisor: 'review',
  devils_advocate_node: 'review', human_gate: 'output',
  final_recommendation: 'output', review: 'output',
};

const GROUP_LABELS: Record<string, string> = {
  input: '输入', parse: '解析', search: '检索', filter: '筛选',
  verify: '验证', repair: '修复', expand: '展开', extract: '提取',
  audit: '审计', assess: '评估', gate: '决策', analyze: '分析',
  review: '审查', output: '输出',
};

const GROUP_ORDER = ['input', 'parse', 'search', 'filter', 'verify', 'repair', 'expand', 'extract', 'audit', 'assess', 'gate', 'analyze', 'review', 'output'];

export function getGroup(node: string): string {
  return NODE_GROUPS[node] || 'unknown';
}

export function getGroupLabel(group: string): string {
  return GROUP_LABELS[group] || group;
}

export function getGroupOrder(): string[] {
  return GROUP_ORDER;
}
```

---

### Phase 3：首页 — 1h

#### Fix 3.1: 首页组件

**文件**：`apps/web-react/src/pages/Home.tsx`

设计原则（借鉴 academic-research-skills `progress_dashboard_template.md` 阶段展示思想，B 级）：

```
┌────────────────────────────────────────────┐
│              PaperAgent                     │
│        题目研究智能工作台                    │
│                                              │
│    输入一个题目，获得完整的证据链和          │
│    可行性分析报告                            │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 1.输入题目│  │ 2.智能检索 │  │ 3.审核报告│   │
│  │  AI分解   │  │  多源验证  │  │  导出报告 │   │
│  └──────────┘  └──────────┘  └──────────┘   │
│                                              │
│  ┌─────────────────────────────────────┐     │
│  │ 🔍 输入题目...          [开始研究]  │     │
│  └─────────────────────────────────────┘     │
│                                              │
│  快速体验：                                   │
│  ┌──────────────┐  ┌──────────────┐          │
│  │ Demo: YOLO   │  │ Demo: 医学AI  │          │
│  │ 钢材缺陷检测  │  │  问答可信度   │          │
│  └──────────────┘  └──────────────┘          │
│                                              │
│  最近研究：[历史 case 列表]                   │
└────────────────────────────────────────────┘
```

**关键交互**：
- 题目输入框 + "开始研究"按钮 → 调 `submitTopic()` → 跳转 `/workbench?case_id=xxx`
- 两个 Demo Case 卡片 → 预填题目，一键开始
- 历史记录下拉 → 点击加载已有 case 的工作台
- 键盘可达：Tab 导航，Enter 提交

**空状态**：无历史记录时显示"还没有研究记录，输入题目开始第一次研究"

#### Fix 3.2: Demo Case 预设

```typescript
const DEMO_CASES = [
  {
    title: '基于YOLO的钢材表面缺陷检测',
    description: '工业视觉质检场景，有公开数据集和 baseline',
    label: '工科 · 计算机视觉',
  },
  {
    title: '基于大语言模型的医学问答可信度评估方法研究',
    description: '医学AI合规场景，涉及安全性和可信度',
    label: '医学 · AI安全',
  },
];
```

---

### Phase 4：工作台 — 2h

#### Fix 4.1: 工作台布局

**文件**：`apps/web-react/src/pages/Workbench.tsx`

```
┌──────────────────────────────────────────────────────────┐
│ ← 返回首页    工作台    [重新开始]                        │
├──────────────────────────────────────────────────────────┤
│ 题目：基于YOLO的钢材表面缺陷检测                          │
│ Case ID: re41-verify-001                  ⏱ 已运行 215s   │
├──────────────────────────────────────────────────────────┤
│ ┌─ 进度条 ──────────────────────────────────────────────┐│
│ │ 输入→解析→检索→筛选→验证→评估→分析→审查→输出        ││
│ │ ████████████████████░░░░░░░░░░  80%                   ││
│ └─────────────────────────────────────────────────────┘│
│                                                          │
│ ┌─ 当前状态 ───────────────────────────────────────────┐ │
│ │ 🔄 正在：论文验证（第 2 轮）                         │ │
│ │ 已收集：9 篇论文 · 12 个仓库 · 3 个数据集            │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ ┌─ 来源状态 ──────────────────────────────────────────┐ │
│ │ arXiv     ✅ 8 篇    Crossref  ✅ 3 篇               │ │
│ │ GitHub    ✅ 12 个   HuggingFace ⚠️ 0 个             │ │
│ │ OpenAlex  ⏭ 已跳过  Semantic Scholar ⏭ 已跳过       │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ ┌─ 论文列表 ──────────────────────────────────────────┐ │
│ │ ✅ 基于深度学习的钢材表面缺陷检测综述 (arXiv 2023)   │ │
│ │ ⚠️  YOLOv8 工业缺陷检测改进 (Crossref 2024)         │ │
│ │ ❌ [已排除] 不相关论文                                │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ ▶ 最终报告（完成后展开）                                 │
│ ▶ 证据图谱                                               │
│ ▶ 工作包                                                 │
│ ▶ 研究叙事                                               │
│ ▶ 创新点                                                 │
│ ▶ 优化方向                                               │
│ ▶ 执行轨迹                                               │
└──────────────────────────────────────────────────────────┘
```

#### Fix 4.2: SSE 状态管理

使用 `useReducer` 管理 SSE 事件流：

```typescript
interface WorkbenchState {
  phase: 'idle' | 'searching' | 'filtering' | 'verifying' | 'expanding' | 'analyzing' | 'done' | 'error';
  currentNode: string | null;
  papers: Paper[];
  repos: RepoCandidate[];
  datasets: DatasetCandidate[];
  counts: { papers: number; accept: number; weak: number; reject: number; expanded: number; repos: number; datasets: number };
  sourceStatus: { perAdapter: Record<string, number>; failed: string[]; skipped: string[] };
  completedNodes: string[];
  elapsedTime: number;
  error: { node: string; message: string } | null;
}
```

**事件处理优先级**（借鉴 AutoResearchClaw 事件分层思想，B 级）：
1. `error` → 立即切换到 error phase，展示错误 + 建议动作
2. `done` → 切换到 done phase，拉取完整 state 渲染报告区
3. `node_current` → 更新 currentNode + 进度条
4. `papers_update` → 追加论文卡片
5. `adapter_status` → 更新来源面板
6. `verify_completed` / `candidate_count` → 更新计数
7. `node_complete` → 记录完成节点

#### Fix 4.3: 人话状态翻译

```typescript
function getHumanStatus(state: WorkbenchState): string {
  if (state.error) return `出错了：${state.error.message}`;
  switch (state.phase) {
    case 'searching': return `正在检索论文（第 ${state.counts.searchStep || 1} 轮）`;
    case 'filtering': return `正在筛选 ${state.counts.papers} 篇候选论文`;
    case 'verifying': return `正在验证论文质量（第 ${state.verifyRound} 轮）`;
    case 'expanding': return `正在展开引用网络（${state.counts.expanded} 篇）`;
    case 'analyzing': return '正在分析可行性和创新点';
    case 'done': return `研究完成，用时 ${state.elapsedTime.toFixed(0)} 秒`;
    default: return '准备中...';
  }
}
```

#### Fix 4.4: 来源面板

```typescript
// SourcePanel.tsx
// 展示每个来源的：名称、状态图标、结果数量
// ✅ 成功 (count) | ⚠️ 警告 (0 results) | ❌ 失败 | ⏭ 已跳过
// 来源名称用中文：arXiv→arXiv、crossref→Crossref、github→GitHub 等
```

#### Fix 4.5: 最终报告折叠区

完成（`done` 事件）后拉取 `GET /{case_id}/state`，渲染以下折叠区：

```typescript
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
```

每个 section 用 `<details>` 折叠，默认展开前 3 个。

#### Fix 4.6: 统一空/错误/加载状态

**`EmptyState.tsx`**：
```typescript
interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}
```

**`ErrorState.tsx`**：
```typescript
interface ErrorStateProps {
  title: string;
  message: string;
  suggestion?: string;  // 建议动作
  onRetry?: () => void;
}

// 错误码 → 中文建议
const ERROR_SUGGESTIONS: Record<string, string> = {
  '400': '请检查输入的题目是否为空或包含非法字符',
  '404': '该研究记录不存在，可能已被清理',
  '429': 'API 调用频率过高，请稍后重试',
  '500': '服务器内部错误，请查看后端日志',
  'timeout': '请求超时，可能是 LLM 或外部 API 响应慢，请重试',
  'network': '网络连接失败，请确认后端服务是否在运行',
};
```

**`LoadingDots.tsx`**：
```typescript
// 三点跳动动画，附中文提示文字
// "正在分析..." / "正在检索..." / "正在验证..."
```

---

### Phase 5：RAG 占位 + 路由 — 30min

#### Fix 5.1: RAG 占位页

**文件**：`apps/web-react/src/pages/RagPlaceholder.tsx`

```typescript
export function RagPlaceholder() {
  return (
    <EmptyState
      icon="📚"
      title="RAG 问答功能即将上线"
      description="基于全文的检索增强问答将在 Re4.5–Re4.6 交付。届时你可以上传 PDF，针对论文内容提问并获得带页码引用的回答。"
      action={{ label: '返回首页', onClick: () => navigate('/') }}
    />
  );
}
```

#### Fix 5.2: 路由配置

**文件**：`apps/web-react/src/router.tsx`

```typescript
import { createBrowserRouter } from 'react-router-dom';
import { Home } from './pages/Home';
import { Workbench } from './pages/Workbench';
import { RagPlaceholder } from './pages/RagPlaceholder';

export const router = createBrowserRouter([
  { path: '/', element: <Home /> },
  { path: '/workbench', element: <Workbench /> },
  { path: '/workbench/:caseId', element: <Workbench /> },
  { path: '/rag', element: <RagPlaceholder /> },
]);
```

#### Fix 5.3: 公共布局

**文件**：`apps/web-react/src/components/Layout.tsx`

```typescript
// 顶部导航栏：PaperAgent logo | 首页 | 工作台 | RAG (disabled style)
// 移动端：汉堡菜单
// 键盘可达：nav 有 aria-label，链接有 focus-visible 样式
```

---

### Phase 6：Playwright 截图基线 — 1h

#### Fix 6.1: Vite 生产构建

```bash
cd apps/web-react
npm run build
# 产出 apps/web-react/dist/
```

#### Fix 6.2: FastAPI 挂载 React 构建（可选）

**文件**：`apps/api/app/main.py`

追加 React 构建的静态挂载（在 `/web` 之后）：

```python
# React 前端（如已构建）
_react_dist = _APP_DIR / "../../web-react/dist"
if _react_dist.exists():
    app.mount("/react", StaticFiles(directory=str(_react_dist), html=True), name="react")
```

> 开发时用 Vite dev server（18183），proxy `/api` → 18181；
> 验收时用构建产物挂载在 `/react`，或直接 dev server 截图。

#### Fix 6.3: Playwright 测试

**文件**：`apps/web-react/e2e/test_re42_react_web.py`

```python
"""Re4.2 Day 2: React+Vite 前端 Playwright 截图基线。

Tests:
1. Home page loads, shows title, 3-step guide, demo cases
2. Workbench: submit topic, see progress, papers, source panel
3. Error state: invalid case_id shows error + suggestion
4. Report: completed case shows report sections
5. Mobile viewport: core flows browsable on 375px width
6. Keyboard nav: Tab through home → demo → workbench
"""
import pytest
import re
from pathlib import Path
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.react_web

BASE_URL = "http://127.0.0.1:18183"
SCREENSHOT_DIR = Path("tmp_re42_screenshots")


class TestReactHome:
    def test_home_loads(self, page: Page):
        """首页加载，显示标题、三步引导、Demo Case。"""
        page.goto(BASE_URL + "/")
        expect(page.locator("h1")).to_contain_text("PaperAgent")
        # 三步引导
        expect(page.locator("text=输入题目")).to_be_visible()
        expect(page.locator("text=智能检索")).to_be_visible()
        expect(page.locator("text=审核报告")).to_be_visible()
        # Demo Case 卡片
        expect(page.locator("text=钢材表面缺陷检测")).to_be_visible()
        SCREENSHOT_DIR.mkdir(exist_ok=True)
        page.screenshot(path=str(SCREENSHOT_DIR / "home.png"))

    def test_home_keyboard_nav(self, page: Page):
        """键盘可达：Tab 导航到开始研究按钮。"""
        page.goto(BASE_URL + "/")
        page.keyboard.press("Tab")  # skip nav links
        page.keyboard.press("Tab")  # focus topic input
        expect(page.locator("input[placeholder*='题目']")).to_be_focused()

    def test_home_mobile_viewport(self, page: Page):
        """窄屏可浏览。"""
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(BASE_URL + "/")
        expect(page.locator("h1")).to_be_visible()
        page.screenshot(path=str(SCREENSHOT_DIR / "home_mobile.png"))


class TestReactWorkbench:
    def test_workbench_submit_topic(self, page: Page):
        """提交题目，看到进度状态。"""
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(BASE_URL + "/")
        page.fill("input[placeholder*='题目']", "基于YOLO的钢材表面缺陷检测")
        page.click("button:has-text('开始研究')")
        # 应跳转到 workbench
        page.wait_for_url("**/workbench**", timeout=5000)
        # 进度区域出现
        expect(page.locator("text=正在")).to_be_visible(timeout=10000)
        page.screenshot(path=str(SCREENSHOT_DIR / "workbench_running.png"))

    def test_workbench_error_state(self, page: Page):
        """无效 case_id 显示错误状态。"""
        page.goto(BASE_URL + "/workbench/invalid-../../etc")
        expect(page.locator("text=错误")).to_be_visible(timeout=5000)
        page.screenshot(path=str(SCREENSHOT_DIR / "workbench_error.png"))

    def test_workbench_completed_case(self, page: Page):
        """已完成 case 显示报告区。"""
        # 先通过 API 列出已有 case
        # 选择一个 completed case
        page.goto(BASE_URL + "/workbench")
        # 从历史记录选择一个
        page.screenshot(path=str(SCREENSHOT_DIR / "workbench_report.png"))

    def test_workbench_mobile(self, page: Page):
        """窄屏工作台可浏览。"""
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(BASE_URL + "/workbench")
        expect(page.locator("h1, h2, .title")).to_be_visible(timeout=5000)
        page.screenshot(path=str(SCREENSHOT_DIR / "workbench_mobile.png"))


class TestReactRagPlaceholder:
    def test_rag_placeholder(self, page: Page):
        """RAG 占位页面。"""
        page.goto(BASE_URL + "/rag")
        expect(page.locator("text=RAG")).to_be_visible()
        expect(page.locator("text=即将上线")).to_be_visible()
        page.screenshot(path=str(SCREENSHOT_DIR / "rag_placeholder.png"))
```

#### Fix 6.4: pytest.ini markers 更新

确认 `react-web` marker 描述已更新（Re4.1 已完成）：
```ini
react-web: Playwright e2e for React+Vite frontend (apps/web-react on 18183)
```

#### Fix 6.5: start_frontend.bat 更新（可选）

追加 React dev server 启动选项：

```batch
:: Option: React dev server (port 18183)
:: cd /d "G:\PaperAgent\apps\web-react"
:: start "PaperAgent React" cmd /k "npm run dev"
```

---

### Phase 7：验收与端到端验证 — 1h

#### Step 1: 构建验证

```bash
cd apps/web-react
npm run build
# 预期：tsc 零 error，dist/ 产出 index.html + assets/
```

#### Step 2: 开发服务器验证

```bash
# Terminal 1: 后端
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181

# Terminal 2: Vite dev server
cd apps/web-react && npm run dev
# 预期：http://127.0.0.1:18183 可访问
```

#### Step 3: pytest 收集不退化

```bash
cd G:\PaperAgent
.venv\Scripts\python.exe -m pytest --collect-only -q 2>&1 | Select-String "error|collected"
# 预期：0 errors，collected 数 ≥ 418（新增 React e2e 测试）
```

#### Step 4: Playwright 截图基线

```bash
# 先启动后端 + Vite dev server
.venv\Scripts\python.exe -m pytest apps/web-react/e2e/test_re42_react_web.py -v -m "react-web"
# 预期：截图生成在 tmp_re42_screenshots/，测试通过或 smoke 级别
```

#### Step 5: 端到端 Case 验证（强制）

> **规则**：全部 Phase 完成后必须跑一个端到端 case，证明前端完整性未被破坏。

**前置条件**：后端 18181 运行中，Vite dev server 18183 运行中，`.env` 有效 `DEEPSEEK_API_KEY`。

```bash
# 1. 浏览器访问 http://127.0.0.1:18183/
# 2. 输入题目：基于YOLO的钢材表面缺陷检测
# 3. 点击"开始研究"
# 4. 确认跳转到 /workbench
# 5. 确认 SSE 实时进度更新（进度条、当前节点、来源面板、论文卡片）
# 6. 等待完成（~3-4 分钟）
# 7. 确认报告折叠区展开，内容非空
# 8. 截图保存
```

**产物完整性检查清单**：

| 检查项 | 通过标准 |
|---|---|
| 首页加载 | 标题、三步引导、两个 Demo Case 可见 |
| 题目提交 | 点击后跳转 workbench，SSE 连接成功 |
| 进度实时更新 | 进度条移动、当前节点人话显示、来源面板有数据 |
| 论文列表 | SSE papers_update 事件触发卡片追加 |
| 来源面板 | 显示各来源状态（✅/⚠️/⏭），跳过源标记"已跳过" |
| 报告区 | 完成后 9 个折叠区可见，前 3 个默认展开 |
| 错误处理 | 无效 case_id 显示错误 + 中文建议 |
| 窄屏 | 375px 宽度下首页和工作台可浏览 |
| 键盘 | Tab 可导航到主要交互元素 |

**数据正确性自检清单**：

| 维度 | 验证方法 | 通过标准 |
|---|---|---|
| 论文计数 | 前端显示数量 = API state 中 verified_papers 长度 | 数量一致 |
| 来源状态 | 前端显示 skipped = SourcePolicy 中 disabled 的源 | 一致 |
| 可行性 | 前端显示 score + verdict | score 为数值，verdict 中文翻译 |
| 审核状态 | 前端显示 review_status | ACCEPT/MINOR_REVISION/BLOCK 对应中文 |
| 工作包 | 前端展示 work_packages 列表 | ≥ 1 个，每个有标题 |
| 旧前端未受影响 | 访问 `http://127.0.0.1:18181/web/` 仍可用 | 旧前端正常加载 |

> **自我检验**：验收者必须对照上述清单逐项检查实际产物，
> 确认每项通过后再标记 Phase 7 完成。任何一项不通过则回到对应 Phase 修复。

---

## 3. 执行顺序与依赖

```
Phase 1 (Vite 脚手架) ─── 无依赖，立即可做
    │
    ├── Phase 2 (类型 + API 封装) ─── 依赖 Phase 1 目录结构
    │
    ├── Phase 3 (首页) ─── 依赖 Phase 2 的 api.ts
    │
    ├── Phase 4 (工作台) ─── 依赖 Phase 2 的 sse.ts + nodeNames.ts
    │       ├── SSE 状态管理 ─── 依赖 Phase 2
    │       ├── 来源面板 ─── 依赖 Phase 2 SourcePolicy 类型
    │       ├── 论文列表 ─── 依赖 Phase 2 Paper 类型
    │       └── 报告折叠区 ─── 依赖 Phase 2 ResearchState 类型
    │
    ├── Phase 5 (RAG 占位 + 路由) ─── 依赖 Phase 3 + 4 页面组件
    │
    ├── Phase 6 (Playwright) ─── 依赖 Phase 1-5 全部完成
    │
    └── Phase 7 (验收 + 端到端) ─── 依赖全部完成

可并行：
- Phase 3 (首页) 和 Phase 4 (工作台) 可同时开发（不同页面组件）
- Phase 5 (RAG 占位) 可与 Phase 4 后半段并行
- Phase 6 的测试用例可在 Phase 4 开发时同步编写
```

---

## 4. 风险与预案

| 风险 | 触发信号 | 预案 |
|---|---|---|
| Node/npm 未安装或版本过低 | `npm install` 失败 | 要求 Node ≥18；安装 nvm-windows 管理 Node 版本 |
| Vite proxy 不生效 | 前端请求 `/api` 返回 404 | 确认 vite.config.ts proxy 配置；后端 CORS 允许 18183 |
| SSE EventSource 跨域 | `EventSource` 报 CORS error | Vite proxy 已处理；生产构建挂载在同源 `/react` 下 |
| TypeScript strict 报错多 | `tsc` 编译失败 | 分批修复：先 `noUnusedLocals: false`，后续逐步收紧 |
| Playwright 测试不稳定 | SSE 等待超时 | 使用 `page.wait_for_selector` 替代固定 `timeout`；失败时 retry 1 次 |
| React 性能问题（大量论文卡片） | DOM 节点过多导致卡顿 | 论文列表限制 100 条，超出显示"显示前 100 条" |
| 旧前端被意外破坏 | `/web/` 返回 500 | Phase 1-6 不修改 `apps/web/` 任何文件；仅新增 `apps/web-react/` |

---

## 5. 完成标准

- [ ] `apps/web-react/` 存在且 `npm run build` 零 TypeScript error
- [ ] Vite dev server 在 18183 启动，proxy `/api` → 18181 正常
- [ ] 首页显示标题、三步引导、两个 Demo Case、历史记录
- [ ] 工作台提交题目后 SSE 实时更新：进度条、当前节点、来源面板、论文列表
- [ ] 来源面板正确显示 ✅/⚠️/⏭ 状态，跳过源标记"已跳过"
- [ ] 完成后 9 个报告折叠区可见，前 3 个默认展开
- [ ] 无效 case_id 显示错误 + 中文建议动作
- [ ] 375px 窄屏下首页和工作台可浏览
- [ ] Tab 键可导航到主要交互元素
- [ ] RAG 占位页面显示"即将上线"
- [ ] Playwright 截图生成在 `tmp_re42_screenshots/`
- [ ] 旧前端 `http://127.0.0.1:18181/web/` 仍正常可用
- [ ] `pytest --collect-only` 零 error
- [ ] `ruff check apps/api/app` ≤ 18 errors（无新增）
- [ ] **端到端 case 跑通**：前端提交题目 → SSE 进度 → 报告展示完整
- [ ] **数据正确性自检**：前端显示数据与 API state 一致

---

## 6. 提交清单

| 文件 | 操作 |
|---|---|
| `apps/web-react/package.json` | 新建 |
| `apps/web-react/vite.config.ts` | 新建 |
| `apps/web-react/tsconfig.json` | 新建 |
| `apps/web-react/tsconfig.node.json` | 新建 |
| `apps/web-react/index.html` | 新建 |
| `apps/web-react/src/main.tsx` | 新建 |
| `apps/web-react/src/App.tsx` | 新建 |
| `apps/web-react/src/router.tsx` | 新建 |
| `apps/web-react/src/types/api.ts` | 新建 |
| `apps/web-react/src/lib/api.ts` | 新建 |
| `apps/web-react/src/lib/sse.ts` | 新建 |
| `apps/web-react/src/lib/nodeNames.ts` | 新建 |
| `apps/web-react/src/components/Layout.tsx` | 新建 |
| `apps/web-react/src/components/EmptyState.tsx` | 新建 |
| `apps/web-react/src/components/ErrorState.tsx` | 新建 |
| `apps/web-react/src/components/LoadingDots.tsx` | 新建 |
| `apps/web-react/src/components/SourcePanel.tsx` | 新建 |
| `apps/web-react/src/pages/Home.tsx` | 新建 |
| `apps/web-react/src/pages/Workbench.tsx` | 新建 |
| `apps/web-react/src/pages/RagPlaceholder.tsx` | 新建 |
| `apps/web-react/src/styles/global.css` | 新建 |
| `apps/web-react/e2e/test_re42_react_web.py` | 新建 |
| `.gitignore` | 追加 web-react node_modules/dist |
| `apps/api/app/main.py` | 追加 /react 静态挂载（可选） |
| `CHANGELOG.md` | 追加 Re4.2 条目 |

---

## 7. CHANGELOG 预备

```markdown
## [0.4.0-dev] - 2026-07-10 (Re4.2)

### Added
- `apps/web-react/`: 最小 React + Vite + TypeScript 前端 shell
  - 首页：价值主张、三步引导、两个 Demo Case 入口、历史记录
  - 工作台：题目输入、SSE 实时进度、论文列表、来源状态面板、报告折叠区
  - RAG 占位路由
  - 统一空状态、错误状态 + 中文建议、加载语义、键盘可达性
  - 人话节点名映射（24 节点 → 中文描述 + 阶段分组）
- `apps/web-react/e2e/test_re42_react_web.py`: Playwright 截图基线（home/workbench/error/report/mobile/keyboard）
- `apps/web-react/src/types/api.ts`: 完整 API 类型定义（ResearchState + SSE + SourcePolicy + Trace）
- `apps/web-react/src/lib/sse.ts`: SSE EventSource 封装（14 事件类型）
- `apps/web-react/src/lib/nodeNames.ts`: 节点内部名 → 人话映射 + 阶段分组

### Changed
- `.gitignore`: 追加 web-react node_modules/dist
- `apps/api/app/main.py`: 追加 /react 静态挂载（构建产物）
- `CHANGELOG.md`: 追加 Re4.2 条目

### Verified
- 端到端 case 前端验证：提交题目 → SSE 进度 → 报告展示完整
- 旧前端 /web/ 未受影响
- 375px 窄屏可浏览
- 键盘 Tab 导航可用
```
