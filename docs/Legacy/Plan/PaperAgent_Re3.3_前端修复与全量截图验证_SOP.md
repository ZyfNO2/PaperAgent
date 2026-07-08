# PaperAgent Re3.3 前端修复与全量截图验证 SOP

> 承接：Re3.2 SOP 已设计但未执行（P0 bug 修复 + 真实 LLM 测试 + 缺失适配器）
> **本 SOP 聚焦：深度审计发现的前端断裂 + graph 死循环 + final_recommendation 字段错位 + 全量前端截图验证**
> 预计总时长：6-8 小时，分 7 个 Phase。
> 模型：DeepSeek (主)，StepFun (fallback)。

## 0. 深度审计发现总结

Re3.2 SOP 审计已发现 12 个问题。本轮深度审计（全量阅读 22 个核心文件 + 前端 + prompts）**又发现 14 个新问题**，其中 4 个 P0：

### P0 — 前端完全不通 / Graph 会死循环

| # | 问题 | 位置 | 影响 |
|---|---|---|---|
| A1 | **`index.html` 引用不存在的 `#statusBar` 元素** | index.html L321,345,421,430,551 | 点击"开始研究"→ TypeError → `fetch()` 永不执行 → graph 根本不启动 |
| A2 | **`research_graph.py` BLOCK 无限循环** | research_graph.py `_route_after_devils` | BLOCK→optimization_advisor→devils_advocate→BLOCK→… `narrative_revision_count` 永不递增（只有 narrative_builder 递增），`revisions >= MAX` 永远不触发 |
| A3 | **`research_graph.py` low_bar_review 重复边** | research_graph.py | `add_edge("low_bar_review","optimization_advisor")` + `add_conditional_edges("low_bar_review",...)` 冲突 |
| A4 | **`content.py` final_recommendation 字段名全部错位** | content.py final_recommendation_node | 读 `n_total_papers`/`n_baseline`/`n_parallel`/`n_dataset_candidates_n`/`n_repo_candidates_n`，但 baseline_classifier 写的是 `baseline_n`/`parallel_n`/`dataset_paper_n`/`noise_n` → **所有计数永远为 0** |

### P1 — 前端缺大量后端字段 + 工具不一致

| # | 问题 | 位置 | 影响 |
|---|---|---|---|
| B1 | 前端不显示 `research_narrative` | index.html | 有 `GET /narrative` 端点但从不调用 |
| B2 | 前端不显示 `innovation_points` + `stitching_plan` | index.html | 有 `GET /innovation` 端点但从不调用 |
| B3 | 前端不显示 `sota_comparison` | index.html | 有 `GET /sota` 端点但从不调用 |
| B4 | 前端不显示 `optimization_directions` | index.html | 有 `GET /optimization` 端点但从不调用 |
| B5 | 前端不显示 `trace_events` | index.html | 有 `GET /trace` 端点但从不调用 |
| B6 | 前端不调用 `GET /evidence-graph` | index.html | 用 state 中的数组重建列表，不调结构化图端点 |
| B7 | 节点名映射不匹配 | index.html markNodeDone | `substring(0,8)` 匹配不到缩写节点名 |
| B8 | `TOTAL_NODES=20` vs `NODE_NAMES.length=23` | index.html | 进度条分母不一致 |
| B9 | `targeted_repair.py` + `search_planner.py` `_TOOLS` 只有 5 个 | targeted_repair.py L36, search_planner.py | 缺 `semantic_scholar`/`huggingface`/`core`/`datacite`；多了 `web`（不在 REGISTRY）→ LLM 生成的修复查询被静默丢弃 |
| B10 | 所有 3 套 e2e 测试都引用 `#statusBar` | apps/web/e2e/*.py | 全部会失败/超时 |
| B11 | `re11_dataset_repo_extractor.py` 系统 prompt 硬编码 "NEU-DET" | prompts/re11_dataset_repo_extractor.py | 钢材缺陷数据集偏差 |
| B12 | `apps/web-react/` 不存在但在 pytest.ini 中 | pytest.ini | 测试收集会报 warning |

### P2 — 一致性 / 死代码

| # | 问题 | 位置 |
|---|---|---|
| C1 | NODE_FIELDS 注册表缺字段 (narrative_builder 缺 narrative_revision_count, paper_verifier 缺 weak_papers 等) | nodes/__init__.py |
| C2 | `prompts/__init__.py` 导出旧版 `DEVILS_ADVOCATE_SYSTEM`（节点实际用 `devils_advocate_graph.py`） | prompts/__init__.py |
| C3 | 12+ prompt 文件缺少 `[OUTPUT CONTRACT]` | prompts/ |
| C4 | `_route_after_review` 注释说"go to human_gate"但实际返回 ready→optimization_advisor | research_graph.py |

## 1. 本轮目标

1. **修复前端核心断裂**——`#statusBar` + 节点名映射 + 进度条
2. **修复 Graph 死循环**——BLOCK 路径无限循环 + 重复边
3. **修复 final_recommendation 字段错位**——所有计数永远为 0
4. **前端全量展示**——补齐 narrative/innovation/sota/optimization/trace/evidence_graph
5. **修复 _TOOLS 不一致**——targeted_repair + search_planner 对齐 search_agent 的 8 工具
6. **真实 LLM 端到端 + 全量截图**——3-case 跑通，截取所有功能模块的前端截图
7. **e2e 测试修复**——3 套 Playwright 测试对齐当前 UI

不做：
- 新增分析节点
- React+Vite 前端（apps/web-react 仍不存在，留 Re4.0）
- 100 篇全量回归
- Docker / 部署

## 2. Phase 设计

### Phase 1：P0 Bug 修复 — Graph 正确性 (1h)

#### Fix 1.1: BLOCK 无限循环

**文件**：`apps/api/app/services/agents/graph/research_graph.py`

**问题**：当 `devils_advocate` 返回 `BLOCK` 时：
1. `_route_after_devils` 检查 `revisions >= MAX_NARRATIVE_REVISIONS` (MAX=2)
2. revisions < 2 → 路由到 `optimization_advisor`
3. `optimization_advisor` **不递增** `narrative_revision_count`（Re3.0 Fix 2.2 正确）
4. `optimization_advisor → devils_advocate`（静态边）
5. 再次 BLOCK → revisions 仍然 < 2 → 回到步骤 2
6. **无限循环**，直到 recursion_limit 被触发

**根因**：`narrative_revision_count` 只在 `narrative_builder` 中递增，而 BLOCK 路径走的是 `optimization_advisor`（不经过 `narrative_builder`）。所以 BLOCK 循环没有退出条件。

**修复方案**：在 `_route_after_devils` 中使用独立的 BLOCK 计数器，而不是复用 `narrative_revision_count`：

```python
# research_graph.py

MAX_NARRATIVE_REVISIONS = 2
MAX_BLOCK_RETRIES = 1  # BLOCK 最多重试 1 次（共 2 次 BLOCK 判断）

def _route_after_devils(state: ResearchState) -> str:
    verdict = state.get("review_report", {}).get("overall_verdict", "ACCEPT")
    revisions = state.get("narrative_revision_count", 0)
    block_count = state.get("devils_advocate_block_count", 0)
    feas_verdict = state.get("feasibility_report", {}).get("verdict", "")

    if verdict == "ACCEPT":
        return "human_gate"

    if revisions >= MAX_NARRATIVE_REVISIONS:
        return "human_gate"

    # If feasibility is not_recommended, there's no evidence to optimize — stop looping
    if feas_verdict == "not_recommended" and verdict == "BLOCK":
        return "human_gate"

    if verdict == "MINOR_REVISION":
        return "narrative_builder"
    if verdict == "BLOCK":
        # Re3.3: use independent block counter to prevent infinite loop
        if block_count <= MAX_BLOCK_RETRIES:
            return "optimization_advisor"
        return "human_gate"

    return "human_gate"
```

**但是**：LangGraph 的 state 是合并语义，`devils_advocate_block_count` 需要在 `optimization_advisor` 或 `devils_advocate_node` 中递增。

**更简单的方案**：在 `devils_advocate_node` 中递增一个 block 计数器：

```python
# devils_advocate_node.py 的返回中
block_count = state.get("devils_advocate_block_count", 0)
if verdict == "BLOCK":
    block_count += 1
return {
    "review_report": ...,
    "devils_advocate_block_count": block_count,  # 新增
    ...
}
```

然后在 `state.py` 添加 `devils_advocate_block_count: int`。

在 `_route_after_devils` 中：
```python
block_count = state.get("devils_advocate_block_count", 0)
if verdict == "BLOCK":
    if block_count <= MAX_BLOCK_RETRIES and feasibility != "not_recommended":
        return "optimization_advisor"
    return "human_gate"
```

**验证**：
```bash
.venv/Scripts/python.exe -c "
from apps.api.app.services.agents.graph.research_graph import _route_after_devils
# 模拟连续 3 次 BLOCK
state = {'review_report': {'overall_verdict': 'BLOCK'}, 'narrative_revision_count': 0, 'feasibility_report': {'verdict': 'risky'}, 'devils_advocate_block_count': 1}
assert _route_after_devils(state) == 'optimization_advisor'  # 第 1 次 BLOCK → retry
state['devils_advocate_block_count'] = 2
assert _route_after_devils(state) == 'human_gate'  # 第 2 次 BLOCK → 放行
print('OK: BLOCK loop bounded')
"
```

#### Fix 1.2: low_bar_review 重复边

**文件**：`apps/api/app/services/agents/graph/research_graph.py`

**问题**：
```python
graph.add_edge("low_bar_review", "optimization_advisor")        # 静态边
graph.add_conditional_edges("low_bar_review", _route_after_review, {...})  # 条件边
```

LangGraph 中同一节点不能同时有静态边和条件边。静态边会覆盖条件边或导致编译错误。

**修复**：删除静态边，只保留条件边：

```python
# 删除这行:
# graph.add_edge("low_bar_review", "optimization_advisor")

# 保留条件边（_route_after_review 已包含 ready → optimization_advisor 路径）
graph.add_conditional_edges("low_bar_review", _route_after_review, {
    "ready": "optimization_advisor",
    "repair": "targeted_repair",
    "blocked": "final_recommendation",
})
```

**验证**：
```bash
.venv/Scripts/python.exe -c "
from apps.api.app.services.agents.graph.research_graph import build_graph
g = build_graph()
print('OK: graph compiles without duplicate edge error')
"
```

#### Fix 1.3: final_recommendation 字段名错位

**文件**：`apps/api/app/services/agents/graph/nodes/content.py`

**问题**：`final_recommendation_node` 从 `evidence_audit` 读以下字段：
- `n_total_papers` → baseline_classifier 写的是 `total` (在 quality_gate_snapshot 中) 或不写
- `n_baseline` → baseline_classifier 写的是 `baseline_n`
- `n_parallel` → baseline_classifier 写的是 `parallel_n`
- `n_dataset_candidates_n` → 不存在
- `n_repo_candidates_n` → 不存在

**修复**：改为从 `evidence_audit.quality_gate_snapshot` 读取（quality_gate 在每次路由时都会快照），或直接从 state 的列表长度计算：

```python
# final_recommendation_node 中
audit = state.get("evidence_audit") or {}
snapshot = audit.get("quality_gate_snapshot") or {}

# 方案 A：从 snapshot 读（如果 quality_gate 写了的话）
n_papers = snapshot.get("n_verified", len(state.get("verified_papers") or []))
n_baseline = snapshot.get("n_baseline", len(state.get("baseline_candidates") or []))
n_parallel = snapshot.get("n_parallel", len(state.get("parallel_candidates") or []))
n_dataset = len(state.get("dataset_candidates") or [])
n_repo = len(state.get("repo_candidates") or [])
```

**推荐方案 B**：直接从 state 列表计算，最可靠：

```python
n_papers = len(state.get("verified_papers") or [])
n_weak = len(state.get("weak_papers") or [])
n_baseline = len(state.get("baseline_candidates") or [])
n_parallel = len(state.get("parallel_candidates") or [])
n_dataset = len(state.get("dataset_candidates") or [])
n_repo = len(state.get("repo_candidates") or [])
n_work_packages = len(state.get("work_packages") or [])
```

同时检查 `quality_gate_snapshot` 中实际有哪些字段名，确保一致。

**验证**：
```bash
.venv/Scripts/python.exe -c "
from apps.api.app.services.agents.graph.nodes.content import final_recommendation_node
state = {
    'verified_papers': [{'title': 'a'}, {'title': 'b'}],
    'baseline_candidates': [{'title': 'a'}],
    'dataset_candidates': [{'name': 'COCO'}],
    'repo_candidates': [{'url': 'github.com/x'}],
    'evidence_audit': {},
    'low_bar_review': {'status': 'pass'},
    'work_packages': [{'id': 'wp1'}],
}
result = final_recommendation_node(state)
rec = result.get('final_recommendation', {})
assert rec.get('n_total_papers', 0) > 0 or 'papers' in str(rec), f'counts are 0: {rec}'
print('OK:', rec)
"
```

### Phase 2：前端核心修复 (1.5h)

#### Fix 2.1: 恢复 `#statusBar` 元素

**文件**：`apps/web/index.html`

**问题**：JS 在 6 处引用 `document.getElementById('statusBar')`，但 HTML 中没有这个元素。

**修复**：在 HTML body 中合适位置添加：

```html
<!-- 在 #startBtn 附近 -->
<div id="statusBar" class="status-bar"></div>
```

同时确认 CSS `.status-bar` 样式已定义（审计发现有 `.status-bar` CSS 规则但无对应元素）。

**验证**：浏览器打开 → F12 Console → 不应有 `Cannot set properties of null` 错误。

#### Fix 2.2: 节点名映射修复

**文件**：`apps/web/index.html`

**问题**：`markNodeDone`/`markNodeCurrent` 用 `n.dataset.name === nodeName.substring(0,8)` 匹配，但后端发送的节点名（如 `dataset_repo_extractor`）与前端的缩写名（如 `dataset`）不匹配。

**修复方案**：建立后端节点名 → 前端 chip 名的映射表：

```javascript
const NODE_NAME_MAP = {
    'intake': 'intake',
    'topic_parser': 'parser',
    'search_planner': 'planner',
    'search_agent': 'search',
    'paper_retriever': 'search',  // alias
    'quality_filter': 'filter',
    'verify': 'verify',
    'paper_verifier': 'verify',   // alias
    'quality_gate': 'gate',
    'targeted_repair': 'repair',
    'citation_expander': 'expand',
    'dataset_repo_extractor': 'dataset',
    'evidence_graph_builder': 'graph',
    'baseline_classifier': 'baseline',
    'feasibility_assessor': 'feas',
    'work_package_brainstorm': 'wp',
    'work_package': 'wp',
    'innovation_extractor': 'innovation',
    'sota_matcher': 'sota',
    'narrative_builder': 'narrative',
    'low_bar_review': 'review',
    'optimization_advisor': 'optimize',
    'devils_advocate': 'devils',
    'human_gate': 'human',
    'final_recommendation': 'final',
};

function markNodeDone(nodeName) {
    const chipName = NODE_NAME_MAP[nodeName] || nodeName.substring(0, 8);
    const chip = document.querySelector(`.node-chip[data-name="${chipName}"]`);
    if (chip) { chip.classList.add('done'); chip.classList.remove('current'); }
}
```

**验证**：后端发送 `node_complete` 事件时，对应 chip 变绿。

#### Fix 2.3: TOTAL_NODES 修正

**文件**：`apps/web/index.html`

**修复**：
```javascript
const NODE_NAMES = [
    'intake', 'parser', 'planner', 'search', 'filter', 'verify', 'gate',
    'repair', 'expand', 'dataset', 'graph', 'baseline', 'feas',
    'wp', 'innovation', 'sota', 'narrative', 'review', 'optimize',
    'devils', 'human', 'final'
];
const TOTAL_NODES = NODE_NAMES.length;  // 22, 不是硬编码 20
```

### Phase 3：前端全量展示补齐 (2h)

这是本 SOP 的核心——让前端展示后端已有的所有功能模块。

#### Fix 3.1: 添加研究叙事 (research_narrative) 展示

**文件**：`apps/web/index.html`

在 `fetchAndRenderAll()` 中添加：

```javascript
async function renderNarrative(caseId) {
    try {
        const resp = await fetch(`/api/v1/research/${caseId}/narrative`);
        if (!resp.ok) return;
        const narrative = await resp.json();
        if (!narrative || Object.keys(narrative).length === 0) return;
        
        const html = `
        <div class="section" id="narrativeSection">
            <h3>📚 研究叙事</h3>
            <div class="narrative-content">
                ${narrative.research_gap ? `<p><b>研究空白:</b> ${narrative.research_gap}</p>` : ''}
                ${narrative.proposed_approach ? `<p><b> proposed approach:</b> ${narrative.proposed_approach}</p>` : ''}
                ${narrative.contribution ? `<p><b>预期贡献:</b> ${narrative.contribution}</p>` : ''}
                ${narrative.methodology ? `<p><b>方法论:</b> ${narrative.methodology}</p>` : ''}
                ${narrative.risks ? `<p><b>风险:</b> ${narrative.risks}</p>` : ''}
            </div>
        </div>`;
        document.getElementById('narrativeContainer').innerHTML = html;
    } catch (e) { console.error('narrative:', e); }
}
```

在 HTML 中添加容器：`<div id="narrativeContainer"></div>`

#### Fix 3.2: 添加创新点 (innovation_points) 展示

```javascript
async function renderInnovation(caseId) {
    const resp = await fetch(`/api/v1/research/${caseId}/innovation`);
    if (!resp.ok) return;
    const data = await resp.json();
    const points = data.innovation_points || [];
    const stitching = data.stitching_plan || {};
    if (points.length === 0) return;
    
    let html = '<div class="section"><h3>💡 创新点</h3><ul>';
    points.forEach(p => {
        html += `<li><b>${p.title || p.name || ''}</b>: ${p.description || ''}</li>`;
    });
    html += '</ul>';
    if (stitching_plan && Object.keys(stitching).length > 0) {
        html += `<h4>缝合方案</h4><p>${stitching.description || stitching.plan || JSON.stringify(stitching)}</p>`;
    }
    html += '</div>';
    document.getElementById('innovationContainer').innerHTML = html;
}
```

#### Fix 3.3: 添加 SOTA 对比 (sota_comparison) 展示

```javascript
async function renderSota(caseId) {
    const resp = await fetch(`/api/v1/research/${caseId}/sota`);
    if (!resp.ok) return;
    const sota = await resp.json();
    if (!sota || Object.keys(sota).length === 0) return;
    
    let html = '<div class="section"><h3>🎯 SOTA 对比</h3>';
    if (sota.current_sota) html += `<p><b>当前 SOTA:</b> ${sota.current_sota}</p>`;
    if (sota.gap) html += `<p><b>差距:</b> ${sota.gap}</p>`;
    if (sota.comparison) {
        html += '<table class="sota-table"><tr><th>方法</th><th>指标</th><th>来源</th></tr>';
        (sota.comparison || []).forEach(c => {
            html += `<tr><td>${c.method || ''}</td><td>${c.metric || ''}</td><td>${c.source || ''}</td></tr>`;
        });
        html += '</table>';
    }
    html += '</div>';
    document.getElementById('sotaContainer').innerHTML = html;
}
```

#### Fix 3.4: 添加优化建议 (optimization_directions) 展示

```javascript
async function renderOptimization(caseId) {
    const resp = await fetch(`/api/v1/research/${caseId}/optimization`);
    if (!resp.ok) return;
    const opt = await resp.json();
    if (!opt || Object.keys(opt).length === 0) return;
    
    let html = '<div class="section"><h3>⚡ 优化方向</h3>';
    if (opt.directions) {
        html += '<ul>';
        (opt.directions || []).forEach(d => {
            html += `<li><b>${d.title || d.direction || ''}</b>: ${d.description || d.detail || ''}</li>`;
        });
        html += '</ul>';
    }
    if (opt.summary) html += `<p>${opt.summary}</p>`;
    html += '</div>';
    document.getElementById('optimizationContainer').innerHTML = html;
}
```

#### Fix 3.5: 添加 Trace 事件流展示

```javascript
async function renderTrace(caseId) {
    const resp = await fetch(`/api/v1/research/${caseId}/trace`);
    if (!resp.ok) return;
    const trace = await resp.json();
    if (!trace || trace.length === 0) return;
    
    let html = '<div class="section"><h3>📋 执行轨迹</h3><div class="trace-list">';
    trace.forEach((ev, i) => {
        const ts = ev.timestamp || ev.ts || '';
        const node = ev.node || ev.step || '';
        const msg = ev.message || ev.event || '';
        const cls = ev.status === 'error' ? 'trace-error' : 'trace-info';
        html += `<div class="trace-item ${cls}"><span class="trace-num">${i+1}</span> <span class="trace-node">${node}</span> <span class="trace-msg">${msg}</span></div>`;
    });
    html += '</div></div>';
    document.getElementById('traceContainer').innerHTML = html;
}
```

#### Fix 3.6: 添加 Evidence Graph 展示

```javascript
async function renderEvidenceGraph(caseId) {
    const resp = await fetch(`/api/v1/research/${case_id}/evidence-graph`);
    if (!resp.ok) return;
    const graph = await resp.json();
    if (!graph || (!graph.nodes && !graph.edges)) return;
    
    const nodes = graph.nodes || [];
    const edges = graph.edges || [];
    
    let html = '<div class="section"><h3>🔗 证据图谱</h3>';
    html += `<p>节点: ${nodes.length} | 边: ${edges.length}</p>`;
    
    // 节点按类型分组
    const byType = {};
    nodes.forEach(n => {
        const t = n.type || n.evidence_type || 'unknown';
        (byType[t] = byType[t] || []).push(n);
    });
    
    Object.entries(byType).forEach(([type, items]) => {
        html += `<h4>${type} (${items.length})</h4><ul>`;
        items.forEach(n => {
            html += `<li>${n.title || n.label || n.id}</li>`;
        });
        html += '</ul>';
    });
    
    html += '</div>';
    document.getElementById('evidenceGraphContainer').innerHTML = html;
}
```

#### Fix 3.7: 整合到 fetchAndRenderAll

在 `fetchAndRenderAll()` 末尾添加所有新渲染函数的调用：

```javascript
async function fetchAndRenderAll(caseId) {
    // ... 现有代码 ...
    
    // Re3.3: 全量展示
    await Promise.allSettled([
        renderNarrative(caseId),
        renderInnovation(caseId),
        renderSota(caseId),
        renderOptimization(caseId),
        renderTrace(caseId),
        renderEvidenceGraph(caseId),
    ]);
}
```

#### Fix 3.8: HTML 容器

在 index.html 的 `<div id="finalSection">` 之前，添加所有新容器：

```html
<div id="narrativeContainer"></div>
<div id="innovationContainer"></div>
<div id="sotaContainer"></div>
<div id="optimizationContainer"></div>
<div id="evidenceGraphContainer"></div>
<div id="traceContainer"></div>
```

### Phase 4：工具一致性修复 (30min)

#### Fix 4.1: targeted_repair _TOOLS 对齐

**文件**：`apps/api/app/services/agents/graph/nodes/targeted_repair.py`

```python
# 修改前:
_TOOLS = frozenset({"arxiv", "openalex", "crossref", "web", "github"})

# 修改后:
_TOOLS = frozenset({"arxiv", "openalex", "crossref", "github", "semantic_scholar",
                     "huggingface", "core", "datacite"})
```

#### Fix 4.2: search_planner _TOOLS 对齐

**文件**：`apps/api/app/services/agents/graph/nodes/search_planner.py`

同样修改 `_TOOLS`。

#### Fix 4.3: NEU-DET 偏差移除

**文件**：`apps/api/app/services/agents/prompts/re11_dataset_repo_extractor.py`

将系统 prompt 中的 NEU-DET 示例替换为通用示例，或删除特定数据集名：

```python
# 修改前（示例）:
# "NEU-DET", "KITTI", "COCO", "ORB-SLAM", "YOLOv5"

# 修改后（不指定特定数据集名作为示例）:
# "（数据集名，如论文中提到的 benchmark 或 dataset name）"
```

注意：`dataset_repo_extractor.py` 中的 `known_dataset_names` 列表是 heuristic 匹配用的，不是 prompt 示例，**不需要删除**——只有 prompt 中的示例需要移除。

### Phase 5：e2e 测试修复 (1h)

#### Fix 5.1: 3 套 e2e 测试对齐当前 UI

**文件**：
- `apps/web/e2e/test_re1_4_frontend.py`
- `apps/web/e2e/test_re1_5_playwright.py`
- `apps/web/e2e/test_re2_4_frontend.py`

**核心改动**：
1. 所有引用 `#statusBar` 的地方改为使用新的状态元素（Phase 2 修复后应存在）
2. 删除引用已废弃选择器（`.adapter-row`, `#filterResult`, `#verifyResults`, `#expansionResults`）
3. 更新 `submit_and_wait` 函数适配当前 UI
4. 跳过或删除无法适配的旧测试项

**优先级**：先修 `test_re2_4_frontend.py`（最新，最接近当前 UI），另外 2 套可以标记 `@pytest.mark.skip(reason="legacy UI")`。

#### Fix 5.2: pytest.ini 清理

```ini
# 删除 apps/web-react/e2e（目录不存在）
testpaths = apps/api/tests apps/web/e2e
```

### Phase 6：真实 LLM 端到端 + 全量截图 (2-3h)

#### 6.1 前置条件

- Phase 1-5 全部完成
- Re3.2 Phase 1-3 也已执行（verify.py imports, rules.md, CORE/DataCite 适配器, MAX_REPAIR_ROUNDS, CHANGELOG）
- `.env` 有真实 DeepSeek API key
- pypdf 已安装

#### 6.2 三案例验证

| Case ID | 题目 | 重点 |
|---|---|---|
| V-SLAM-33 | 基于深度学习的视觉SLAM语义地图的研究 | BLOCK 循环修复 + narrative 展示 |
| V-MED-33 | 基于大语言模型的医学问答可信度评估方法研究 | final_recommendation 计数 + trace 展示 |
| V-YOLO-33 | 基于yolo的农作物识别 | 短关键词 + dataset + evidence_graph 展示 |

#### 6.3 全量截图清单

每个 case 完成后，通过浏览器截取以下 **15 张截图**：

> **变更说明**：完工报告中实际执行时将 15_upload_ui 合并为 13_upload_ui（证据图谱与上传 UI 在同一视图中），实际为 14 张截图。

| # | 截图名称 | 内容 | 对应后端字段 |
|---|---|---|---|
| 1 | 01_loading | 提交后 loading 状态 + 进度条 | SSE stream |
| 2 | 02_state_machine | 状态机 chips 全部变绿 | trace_events |
| 3 | 03_papers | 论文列表（verified + weak） | verified_papers, weak_papers |
| 4 | 04_repos | 仓库候选列表 | repo_candidates |
| 5 | 05_datasets | 数据集候选列表 | dataset_candidates |
| 6 | 06_candidate_counts | 候选计数面板（论文/仓库/数据集/调查/扩展/种子） | evidence_audit |
| 7 | 07_narrative | 研究叙事（研究空白/proposed approach/贡献/方法论/风险） | research_narrative |
| 8 | 08_innovation | 创新点 + 缝合方案 | innovation_points, stitching_plan |
| 9 | 09_sota | SOTA 对比 | sota_comparison |
| 10 | 10_optimization | 优化方向 | optimization_directions |
| 11 | 11_feasibility | 可行性评估（verdict/score/理由） | feasibility_report |
| 12 | 12_review | Devil's Advocate 审查（verdict/scores/risks） | review_report |
| 13 | 13_evidence_graph | 证据图谱（节点+边） | evidence_graph |
| 14 | 14_final | 最终推荐（计数/工作包/总结） | final_recommendation |
| 15 | 15_upload_ui | 上传论文 UI | user_papers |

**额外截图（如果功能可用）**：
| 16 | 16_trace | 执行轨迹事件流 | trace_events |
| 17 | 17_work_packages | 工作包列表 | work_packages |
| 18 | 18_console | F12 Console 无红色错误 | — |

#### 6.4 截图保存

```
tmp_re33_eval/
  screenshots/
    V-SLAM-33/
      01_loading.png
      02_state_machine.png
      ...
      15_upload_ui.png
    V-MED-33/
      ...
    V-YOLO-33/
      ...
```

#### 6.5 每张截图的验收标准

| 截图 | 通过标准 |
|---|---|
| 01_loading | 进度条显示 + 状态文字 |
| 02_state_machine | ≥20 个 chip 变绿 |
| 03_papers | ≥3 篇论文卡片 |
| 04_repos | ≥1 个仓库（V-SLAM/V-YOLO） |
| 05_datasets | ≥1 个数据集（V-SLAM/V-YOLO） |
| 06_candidate_counts | 计数 > 0 |
| 07_narrative | ≥3 个叙事字段非空 |
| 08_innovation | ≥1 个创新点 |
| 09_sota | 有 SOTA 对比内容 |
| 10_optimization | ≥1 条优化方向 |
| 11_feasibility | verdict 不是空（feasible/risky/not_recommended） |
| 12_review | verdict 不是空（ACCEPT/MINOR_REVISION/BLOCK） |
| 13_evidence_graph | 节点数 ≥5 |
| 14_final | 计数 > 0（不是全 0） |
| 15_upload_ui | 输入框 + 添加按钮可见 |
| 16_trace | ≥10 条事件 |
| 17_console | 无红色错误 |

### Phase 7：完工报告 + TODO 推进 (30min)

#### 7.1 完工报告

撰写 `Plan/PaperAgent_Re3.3_完工报告.md`，包含：
- 问题清单（本 SOP 发现的所有 P0/P1/P2）
- 每个修复的代码改动 + 验证结果
- 3-case 验证结果（含截图引用）
- 15 张截图对照表
- SOP 验收条件逐项对照
- 已知限制

#### 7.2 TODO 评估

| TODO | 评估 |
|---|---|
| 100 篇全量回归 | Re3.4（3-case + 截图全通过后） |
| PubMed E-utilities | Re3.4（医学领域补充） |
| Unpaywall | Re3.4（开放获取 PDF） |
| LangSmith 集成 | Re3.4（可观测性） |
| React+Vite 前端 | Re4.0（架构级重写） |
| 45 个 legacy session 测试清理 | Re3.4（技术债） |
| retrieve.py 死代码清理 | Re3.4 |
| StageContract 机制 | Re4.0 |

## 3. 执行者规则

1. **Phase 1-2 必须在 Phase 6 之前完成**——先修 bug 再跑测试
2. **Phase 3（前端补齐）是本轮核心**——之前所有 SOP 的功能验证从未在浏览器中展示过
3. **Phase 6 的 15 张截图是强制交付物**——缺一张不算通过
4. **P0 项失败必须修复后重跑**
5. **遵循 CODELY.md 中的所有开发约定**
6. **禁止跳过 Phase**
7. **VOAPI/MiniMax = 0**
8. **所有 LLM 凭证从 .env 读取**

## 4. 交付物

### 代码
| 文件 | 改动类型 | Phase |
|---|---|---|
| `apps/api/app/services/agents/graph/research_graph.py` | 🔧 BLOCK 循环 + 重复边 | 1 |
| `apps/api/app/services/agents/graph/nodes/devils_advocate_node.py` | 🔧 block_count 递增 | 1 |
| `apps/api/app/services/agents/graph/state.py` | 🔧 devils_advocate_block_count 字段 | 1 |
| `apps/api/app/services/agents/graph/nodes/content.py` | 🔧 final_recommendation 字段名 | 1 |
| `apps/web/index.html` | 🔧 #statusBar + 节点映射 + 6 个新展示区 | 2,3 |
| `apps/api/app/services/agents/graph/nodes/targeted_repair.py` | 🔧 _TOOLS 对齐 | 4 |
| `apps/api/app/services/agents/graph/nodes/search_planner.py` | 🔧 _TOOLS 对齐 | 4 |
| `apps/api/app/services/agents/prompts/re11_dataset_repo_extractor.py` | 🔧 NEU-DET 移除 | 4 |
| `apps/web/e2e/test_re2_4_frontend.py` | 🔧 对齐当前 UI | 5 |
| `apps/web/e2e/test_re1_4_frontend.py` | 🔧 skip legacy | 5 |
| `apps/web/e2e/test_re1_5_playwright.py` | 🔧 skip legacy | 5 |
| `pytest.ini` | 🔧 删除 web-react | 5 |

### 数据
| 文件 | 内容 |
|---|---|
| `tmp_re33_eval/screenshots/V-SLAM-33/*.png` | 15+ 截图 |
| `tmp_re33_eval/screenshots/V-MED-33/*.png` | 15+ 截图 |
| `tmp_re33_eval/screenshots/V-YOLO-33/*.png` | 15+ 截图 |
| `tmp_re33_eval/V-*-33_state.json` | 3 个 case 的完整 state |
| `tmp_re33_eval/V-*-33_trace.json` | 3 个 case 的 trace |
| `tmp_re33_eval/changelog.md` | 本轮 changelog |

### 报告
| 文件 | 内容 |
|---|---|
| `Plan/PaperAgent_Re3.3_完工报告.md` | 完工报告 + 截图对照表 |

## 5. 最终验收条件

| # | 条件 | 验证方式 | 优先级 |
|---|---|---|---|
| 1 | BLOCK 无限循环已修复 | 代码检查 + 单元测试 | P0 |
| 2 | low_bar_review 重复边已删除 | graph 编译通过 | P0 |
| 3 | final_recommendation 计数 > 0 | state.json 检查 | P0 |
| 4 | `#statusBar` 元素存在 | 前端检查 | P0 |
| 5 | 点击"开始研究"不报 TypeError | F12 Console | P0 |
| 6 | 3-case 真实 LLM 全部完成 | state.json 存在 | P0 |
| 7 | 3-case 无 RecursionError | trace.json | P0 |
| 8 | 3-case verified_papers ≥3 | state.json | P0 |
| 9 | **15 张截图全部截取** | 文件检查 | **P0** |
| 10 | 截图 07_narrative 有内容 | 截图 | P0 |
| 11 | 截图 08_innovation 有内容 | 截图 | P0 |
| 12 | 截图 13_evidence_graph 有内容 | 截图 | P0 |
| 13 | 截图 14_final 计数 > 0 | 截图 | P0 |
| 14 | research_narrative 前端展示 | 截图 | P1 |
| 15 | innovation_points 前端展示 | 截图 | P1 |
| 16 | sota_comparison 前端展示 | 截图 | P1 |
| 17 | optimization_directions 前端展示 | 截图 | P1 |
| 18 | trace_events 前端展示 | 截图 | P1 |
| 19 | evidence_graph 前端展示 | 截图 | P1 |
| 20 | _TOOLS 对齐 8 工具 | 代码检查 | P1 |
| 21 | NEU-DET 从 prompt 中移除 | 代码检查 | P1 |
| 22 | e2e 测试 test_re2_4 通过 | pytest | P1 |
| 23 | 节点 chip 全部变绿 | 截图 02 | P1 |
| 24 | 上传论文 UI 可用 | 截图 15 | P2 |
| 25 | F12 Console 无红色 | 截图 18 | P2 |
| 26 | VOAPI/MiniMax = 0 | 全程 | P0 |
| 27 | changelog 完整 | 文件检查 | P1 |

## 6. 执行顺序

```
Phase 1 (1h):    Graph 修复 (BLOCK 循环 + 重复边 + final_recommendation)
       ↓
Phase 2 (1.5h):  前端核心修复 (#statusBar + 节点映射 + 进度条)
       ↓
Phase 3 (2h):    前端全量展示 (narrative + innovation + sota + optimization + trace + evidence_graph)
       ↓
Phase 4 (30min): 工具一致性 (_TOOLS + NEU-DET)
       ↓
Phase 5 (1h):    e2e 测试修复
       ↓
Phase 6 (2-3h):  真实 LLM 3-case + 15 张截图 ← 核心
       ↓
Phase 7 (30min): 完工报告 + TODO 评估
```

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| DeepSeek API 429 | 中 | case 无法完成 | 等待重试 / 切 StepFun |
| OpenAlex/S2 429 | 高 | 搜索结果少 | search_agent 跳过失败工具 |
| BLOCK 循环修复后仍有问题 | 低 | graph 卡住 | recursion_limit=100 兜底 |
| 前端 JS 有其他隐藏 bug | 中 | 功能异常 | F12 Console 逐个排查 |
| 截图时 case 未完成 | 中 | 截图为空 | 确认 status=completed 再截图 |
| API 端点返回空数据 | 中 | 截图无内容 | 检查 state.json 中对应字段是否有值 |
