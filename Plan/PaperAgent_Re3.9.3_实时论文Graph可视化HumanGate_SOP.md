# PaperAgent Re3.9.3 实时论文展示 + Graph 图可视化 + 搜索后 Human Gate SOP

> 承接：Re3.9.2 流式推送修复。用户要求：
> 1. 论文搜出来就实时显示，不需要等验证完成
> 2. 状态机改为 LangGraph 图可视化，能看到当前处于图的哪个位置
> 3. 搜索完成后加 Human Gate，用户确认后才继续分析（调试模式跳过）
> 
> **本 SOP 聚焦：实时论文推送 + Graph 图可视化 + 搜索后人工确认**
> 预计总时长：3-4 小时，分 3 个 Phase。
> 模型：DeepSeek (主)，StepFun (fallback)。

## 0. 现状分析

### 当前前端展示时机

```
提交 → 干等 3-5 分钟 → graph 跑完 → fetchAndRenderAll() 一次性渲染全部
```

论文列表在 `fetchAndRenderAll()` 中从最终 state.json 读取，graph 跑完才显示。

### 当前状态机

扁平 chip 列表（intake → parser → planner → ... → final），不是 graph 拓扑图。无法看出条件分支、循环路径。

### 当前 Human Gate

`human_gate_node` 在 graph 最后（devils_advocate 之后），且默认禁用（`HUMAN_GATE_ENABLED=false`）。用户需要的是在**搜索完成后、分析开始前**加一个 gate。

### Graph 节点顺序

```
intake → topic_parser → search_planner → search_agent → quality_filter 
→ verify → quality_gate → [repair loop / citation_expander / continue]
→ dataset_repo → evidence_graph → baseline_classifier → feasibility
→ work_package → innovation/sota → narrative → low_bar_review
→ optimization → devils_advocate → human_gate → final
```

**新的 gate 位置**：在 `dataset_repo_extractor` 之前，即 quality_gate 通过后、分析阶段开始前。

## 1. 本轮目标

1. **实时论文推送**——search_agent 每搜到一个适配器结果就立即推送前端显示，不等验证
2. **Graph 图可视化**——用 SVG/Canvas 画 LangGraph 拓扑图，高亮当前节点
3. **搜索后 Human Gate**——quality_gate 通过后暂停，用户确认"继续分析"或"停止"
4. **验证**——1 个 case 跑通

不做：
- 重写 SSE 为 WebSocket
- 修改 node 内部逻辑
- 修改 graph 拓扑（gate 用 interrupt 实现，不改边）
- 完整回归测试

## 2. Phase 设计

### Phase 1：实时论文推送 (1h)

#### 设计思路

search_agent 在 ThreadPoolExecutor 中循环调用适配器。每个适配器返回结果后，立即将 `paper_candidates` 和 `repo_candidates` 写入一个**中间 state 文件**（`state_partial.json`），SSE 轮询检测到后推送 `papers_update` 事件，前端实时渲染。

#### Fix 1.1: search_agent 中间结果落盘

**文件**：`apps/api/app/services/agents/graph/nodes/search_agent.py`

在主循环中，每完成一个 tool call 后写入中间状态：

```python
# search_agent_node 主循环中，在 step.append(...) 之后添加：

# Re3.9.3: 实时推送论文——每步完成后写 partial state
import os
_case_id = state.get("case_id", "")
if _case_id:
    _partial_path = os.path.join("tmp_re13_eval", _case_id, "state_partial.json")
    os.makedirs(os.path.dirname(_partial_path), exist_ok=True)
    _partial = {
        "paper_candidates": unique_papers,  # 已去重的
        "repo_candidates": unique_repos,
        "search_steps": steps,
        "last_update": _now_iso(),
    }
    import json as _json
    with open(_partial_path, "w", encoding="utf-8") as _f:
        _json.dump(_partial, _f, ensure_ascii=False, default=str)
```

**注意**：`unique_papers` 和 `unique_repos` 在当前代码中是循环结束后才去重的。需要把去重逻辑移到循环内部——每步都去重并更新。

```python
# 修改去重逻辑——从循环后移到每步后：
# 当前（循环后）:
#   seen_keys = set()
#   unique_papers = [p for p in all_papers if dedup...]
# 改为（每步后）:
#   在 steps.append 之后添加:
    seen_keys: set[str] = set()
    unique_papers = []
    unique_repos = []
    for p in all_papers:
        key = _dedup_key(p)
        if key and key not in seen_keys:
            seen_keys.add(key)
            unique_papers.append(p)
    seen_repo_keys = set()
    for r in all_repos:
        key = _dedup_key(r)
        if key and key not in seen_repo_keys:
            seen_repo_keys.add(key)
            unique_repos.append(r)
```

#### Fix 1.2: SSE 推送 papers_update 事件

**文件**：`apps/api/app/api/v1/research.py`

在 SSE event_generator 的轮询循环中，检测 `state_partial.json` 的变化：

```python
# SSE event_generator 中，在 trace 检查之后添加：

# Re3.9.3: 检查 partial state（实时论文推送）
partial_path = _case_dir(case_id) / "state_partial.json"
if partial_path.exists():
    try:
        partial_mtime = partial_path.stat().st_mtime
        if partial_mtime != last_partial_mtime:
            last_partial_mtime = partial_mtime
            partial = json.loads(partial_path.read_text(encoding="utf-8"))
            papers = partial.get("paper_candidates", [])
            repos = partial.get("repo_candidates", [])
            yield _sse_event("papers_update", {
                "papers": [{"title": p.get("title","")[:80],
                           "source": p.get("source",""),
                           "url": p.get("url","")} for p in papers[:20]],
                "n_papers": len(papers),
                "n_repos": len(repos),
                "search_step": partial.get("search_steps", [{}])[-1].get("step", 0),
            })
    except Exception:
        pass
```

在 event_generator 初始化中添加 `last_partial_mtime = 0`。

#### Fix 1.3: 前端接收 papers_update 事件

**文件**：`apps/web/index.html`

```javascript
// 在 connectSSE 中添加:
es.addEventListener('papers_update', function(e) {
    var d = JSON.parse(e.data);
    // 实时显示论文列表
    document.getElementById('papersPanel').style.display = '';
    var html = '';
    var papers = d.papers || [];
    for (var i = 0; i < papers.length; i++) {
        var p = papers[i];
        html += '<div class="paper-card" style="border-left-color:#3b82f6;">';
        html += '<span class="verdict-icon" style="color:#3b82f6;">⏳</span>';
        html += '<div class="paper-body">';
        html += '<div class="paper-title">' + p.title + '</div>';
        html += '<div class="paper-rel">' + p.source + '</div>';
        html += '</div></div>';
    }
    if (papers.length === 0) {
        html = '<div style="color:#94a3b8;font-size:13px;padding:8px;">搜索中...</div>';
    }
    document.getElementById('paperList').innerHTML = html;
    // 更新计数
    setCount('cnt-papers', d.n_papers);
    setCount('cnt-repos', d.n_repos);
});
```

**效果**：论文卡片逐步出现，蓝色边框 + ⏳ 图标表示"待验证"。graph 跑完后 `fetchAndRenderAll` 会用最终结果替换（绿色 ✓ / 橙色 ⚠）。

### Phase 2：Graph 图可视化 (1.5h)

#### Fix 2.1: Graph 拓扑数据端点

**文件**：`apps/api/app/api/v1/research.py`

新增 `GET /{case_id}/graph-topology` 端点，返回 graph 的节点和边：

```python
@router.get("/{case_id}/graph-topology")
def case_graph_topology(case_id: str) -> dict[str, Any]:
    """Return graph topology for visualization."""
    # 静态拓扑——所有 case 共享同一个 graph 结构
    return {
        "nodes": [
            {"id": "intake", "label": "intake", "x": 50, "y": 50, "group": "input"},
            {"id": "topic_parser", "label": "topic_parser", "x": 50, "y": 120, "group": "parse"},
            {"id": "search_planner", "label": "search_planner", "x": 50, "y": 190, "group": "search"},
            {"id": "search_agent", "label": "search_agent", "x": 50, "y": 260, "group": "search"},
            {"id": "quality_filter", "label": "quality_filter", "x": 50, "y": 330, "group": "filter"},
            {"id": "verify", "label": "verify", "x": 50, "y": 400, "group": "verify"},
            {"id": "quality_gate", "label": "quality_gate", "x": 50, "y": 470, "group": "verify"},
            {"id": "targeted_repair", "label": "repair", "x": 200, "y": 400, "group": "repair"},
            {"id": "citation_expander", "label": "citation", "x": 200, "y": 470, "group": "expand"},
            {"id": "dataset_repo_extractor", "label": "dataset_repo", "x": 50, "y": 540, "group": "extract"},
            {"id": "evidence_graph_builder", "label": "evidence_graph", "x": 50, "y": 610, "group": "audit"},
            {"id": "baseline_classifier", "label": "baseline", "x": 50, "y": 680, "group": "audit"},
            {"id": "feasibility_assessor", "label": "feasibility", "x": 50, "y": 750, "group": "assess"},
            {"id": "human_gate_search", "label": "🔍 Human Gate", "x": 50, "y": 820, "group": "gate"},
            {"id": "work_package", "label": "work_package", "x": 50, "y": 890, "group": "analyze"},
            {"id": "innovation_extractor", "label": "innovation", "x": 20, "y": 960, "group": "analyze"},
            {"id": "sota_matcher", "label": "sota", "x": 80, "y": 960, "group": "analyze"},
            {"id": "narrative_builder", "label": "narrative", "x": 50, "y": 1030, "group": "analyze"},
            {"id": "low_bar_review", "label": "low_bar", "x": 50, "y": 1100, "group": "review"},
            {"id": "optimization_advisor", "label": "optimization", "x": 50, "y": 1170, "group": "review"},
            {"id": "devils_advocate", "label": "devils_adv", "x": 50, "y": 1240, "group": "review"},
            {"id": "human_gate", "label": "human_gate", "x": 50, "y": 1310, "group": "gate"},
            {"id": "final_recommendation", "label": "final", "x": 50, "y": 1380, "group": "output"},
        ],
        "edges": [
            {"from": "intake", "to": "topic_parser"},
            {"from": "topic_parser", "to": "search_planner"},
            {"from": "search_planner", "to": "search_agent"},
            {"from": "search_agent", "to": "quality_filter"},
            {"from": "quality_filter", "to": "verify"},
            {"from": "verify", "to": "quality_gate"},
            {"from": "quality_gate", "to": "targeted_repair", "dashed": True},
            {"from": "quality_gate", "to": "citation_expander", "dashed": True},
            {"from": "quality_gate", "to": "dataset_repo_extractor", "dashed": True},
            {"from": "targeted_repair", "to": "search_agent", "dashed": True, "label": "repair loop"},
            {"from": "citation_expander", "to": "verify", "dashed": True, "label": "expand loop"},
            {"from": "dataset_repo_extractor", "to": "evidence_graph_builder"},
            {"from": "evidence_graph_builder", "to": "baseline_classifier"},
            {"from": "baseline_classifier", "to": "feasibility_assessor"},
            {"from": "feasibility_assessor", "to": "human_gate_search", "dashed": True},
            {"from": "human_gate_search", "to": "work_package"},
            {"from": "work_package", "to": "innovation_extractor"},
            {"from": "work_package", "to": "sota_matcher"},
            {"from": "innovation_extractor", "to": "narrative_builder"},
            {"from": "sota_matcher", "to": "narrative_builder"},
            {"from": "narrative_builder", "to": "low_bar_review"},
            {"from": "low_bar_review", "to": "optimization_advisor", "dashed": True},
            {"from": "optimization_advisor", "to": "devils_advocate"},
            {"from": "devils_advocate", "to": "narrative_builder", "dashed": True, "label": "revision"},
            {"from": "devils_advocate", "to": "human_gate", "dashed": True},
            {"from": "human_gate", "to": "final_recommendation"},
        ],
    }
```

#### Fix 2.2: 前端 SVG Graph 可视化

**文件**：`apps/web/index.html`

替换当前的扁平 chip 列表，改为 SVG graph 图：

```html
<!-- 替换 state-machine div -->
<div class="state-machine">
  <div class="sm-title">Graph 拓扑 <span id="smProgress" style="float:right;font-weight:400">—</span></div>
  <svg id="graphSvg" width="300" height="1400" style="overflow:visible;"></svg>
</div>
```

```css
/* Graph 节点样式 */
.graph-node { cursor: pointer; transition: all .3s; }
.graph-node-rect { fill: #f1f5f9; stroke: #e2e8f0; stroke-width: 1.5; rx: 6; }
.graph-node-rect.done { fill: #dcfce7; stroke: #bbf7d0; }
.graph-node-rect.current { fill: #2563eb; stroke: #1d4ed8; }
.graph-node-rect.gate { fill: #fef3c7; stroke: #f59e0b; }
.graph-node-text { font-size: 10px; text-anchor: middle; dominant-baseline: middle; fill: #475569; pointer-events: none; }
.graph-node-text.done { fill: #16a34a; }
.graph-node-text.current { fill: #fff; font-weight: 600; }
.graph-edge { stroke: #cbd5e1; stroke-width: 1.5; fill: none; }
.graph-edge.dashed { stroke-dasharray: 4 2; }
.graph-edge-label { font-size: 8px; fill: #94a3b8; }
```

```javascript
// 加载 graph topology 并渲染 SVG
var graphTopology = null;
var completedNodes = new Set();

async function loadGraphTopology() {
    try {
        var resp = await fetch('/api/v1/research/graph-topology');
        if (!resp.ok) return;
        graphTopology = await resp.json();
        renderGraph();
    } catch(e) { console.error('topology:', e); }
}

function renderGraph() {
    if (!graphTopology) return;
    var svg = document.getElementById('graphSvg');
    var html = '';

    // 画边
    var edges = graphTopology.edges || [];
    for (var i = 0; i < edges.length; i++) {
        var e = edges[i];
        var fromNode = findNode(e.from);
        var toNode = findNode(e.to);
        if (!fromNode || !toNode) continue;
        var cls = 'graph-edge' + (e.dashed ? ' dashed' : '');
        // 简单直线
        html += '<line class="' + cls + '" x1="' + fromNode.x + '" y1="' + (fromNode.y + 15) + '" x2="' + toNode.x + '" y2="' + (toNode.y - 15) + '"/>';
        if (e.label) {
            var mx = (fromNode.x + toNode.x) / 2;
            var my = (fromNode.y + toNode.y) / 2;
            html += '<text class="graph-edge-label" x="' + (mx + 5) + '" y="' + my + '">' + e.label + '</text>';
        }
    }

    // 画节点
    var nodes = graphTopology.nodes || [];
    for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        var isDone = completedNodes.has(n.id);
        var isCurrent = (n.id === currentNodeId);
        var isGate = (n.group === 'gate');
        var rectCls = 'graph-node-rect';
        if (isCurrent) rectCls += ' current';
        else if (isDone) rectCls += ' done';
        if (isGate) rectCls += ' gate';
        var textCls = 'graph-node-text';
        if (isCurrent) textCls += ' current';
        else if (isDone) textCls += ' done';

        var w = 100, h = 28;
        var x = n.x - w/2;
        var y = n.y - h/2;
        html += '<g class="graph-node" data-node="' + n.id + '">';
        html += '<rect class="' + rectCls + '" x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '"/>';
        html += '<text class="' + textCls + '" x="' + n.x + '" y="' + n.y + '">' + n.label + '</text>';
        html += '</g>';
    }

    svg.innerHTML = html;

    // 点击节点跳转到时间线
    var nodeEls = svg.querySelectorAll('.graph-node');
    nodeEls.forEach(function(el) {
        el.onclick = function() {
            var nodeId = el.getAttribute('data-node');
            // 在时间线中选中对应节点
            if (tlTraceData) {
                for (var i = 0; i < tlTraceData.length; i++) {
                    if (tlTraceData[i].node === nodeId || nodeId.includes(tlTraceData[i].node)) {
                        selectTimelineNode(i);
                        break;
                    }
                }
            }
        };
    });
}

function findNode(id) {
    if (!graphTopology) return null;
    var nodes = graphTopology.nodes || [];
    for (var i = 0; i < nodes.length; i++) {
        if (nodes[i].id === id) return nodes[i];
    }
    return null;
}

var currentNodeId = '';

function markGraphNodeDone(nodeName) {
    completedNodes.add(nodeName);
    // 解析后端节点名到 topology 节点 id
    var mapped = _resolveNodeName(nodeName);
    completedNodes.add(mapped);
    renderGraph();
}

function markGraphNodeCurrent(nodeName) {
    currentNodeId = _resolveNodeName(nodeName);
    completedNodes.add(currentNodeId);
    renderGraph();
    // 滚动到当前节点
    var node = findNode(currentNodeId);
    if (node) {
        var svg = document.getElementById('graphSvg');
        svg.parentElement.scrollTop = node.y - 100;
    }
}
```

在 SSE 事件处理中更新 graph：

```javascript
// node_complete 事件:
es.addEventListener('node_complete', function(e) {
    var d = JSON.parse(e.data);
    markGraphNodeDone(d.node);
    // ... existing nextMap logic ...
});

// node_current 事件 (Re3.9.2):
es.addEventListener('node_current', function(e) {
    var d = JSON.parse(e.data);
    markGraphNodeCurrent(d.node);
});

// papers_update 事件:
es.addEventListener('papers_update', function(e) {
    // ... Fix 1.3 的逻辑 ...
    // 同时标记 search_agent 为 current
    markGraphNodeCurrent('search_agent');
});
```

#### Fix 2.3: 初始化加载

```javascript
// 页面加载时加载 topology
loadGraphTopology();
```

### Phase 3：搜索后 Human Gate (1h)

#### Fix 3.1: 新增 human_gate_search 节点

**文件**：`apps/api/app/services/agents/graph/nodes/content.py`

新增一个在 feasibility_assessor 之后、work_package 之前的 gate 节点：

```python
def human_gate_search_node(state: ResearchState) -> dict[str, Any]:
    """Human gate after search+verify, before analysis.

    Pauses execution to let user review search results.
    In debug mode (HUMAN_GATE_ENABLED=false), passes through automatically.
    """
    import os
    enabled = os.environ.get("HUMAN_GATE_ENABLED", "false").lower() == "true"
    t0 = time.time()

    if enabled:
        from langgraph.types import interrupt
        try:
            decision = interrupt({
                "kind": "human_gate_search",
                "message": "搜索阶段完成，请确认是否继续分析",
                "n_verified": len(state.get("verified_papers") or []),
                "n_weak": len(state.get("weak_papers") or []),
                "n_repos": len(state.get("repo_candidates") or []),
                "n_datasets": len(state.get("dataset_candidates") or []),
                "feasibility_verdict": (state.get("feasibility_report") or {}).get("verdict", ""),
                "feasibility_score": (state.get("feasibility_report") or {}).get("score", 0),
            })
            gate = {"status": "confirmed", "decision": decision}
        except RuntimeError:
            gate = {"status": "pass_through_no_runtime", "reason": "no checkpointer"}
    else:
        gate = {"status": "pass_through", "reason": "debug mode (HUMAN_GATE_ENABLED!=true)"}

    trace = _emit("human_gate_search", t0, {"enabled": enabled, "n_papers": len(state.get("verified_papers") or [])},
                  {"status": gate["status"]}, [], "local", [],
                  state_keys=["human_gate_search", "trace_events"])
    return {"human_gate_search": gate, "trace_events": [trace]}
```

#### Fix 3.2: 注册到 graph

**文件**：`apps/api/app/services/agents/graph/nodes/__init__.py`

```python
from ..content import human_gate_search_node
REGISTRY["human_gate_search"] = human_gate_search_node
```

**文件**：`apps/api/app/services/agents/graph/research_graph.py`

修改边——feasibility_assessor 之后插入 gate：

```python
# 修改前:
# graph.add_conditional_edges("feasibility_assessor", _route_after_feasibility, {
#     "work_package": "work_package",
#     "optimization_advisor": "optimization_advisor",
# })

# 修改后:
graph.add_conditional_edges("feasibility_assessor", _route_after_feasibility, {
    "work_package": "human_gate_search",      # Re3.9.3: 先过 gate
    "optimization_advisor": "optimization_advisor",  # risky 直接到 optimization
})
graph.add_edge("human_gate_search", "work_package")  # gate 通过后进入 work_package
```

#### Fix 3.3: 前端 gate UI

**文件**：`apps/web/index.html`

当 SSE 推送 `human_gate_search` 的 `node_current` 事件时，显示确认按钮：

```javascript
es.addEventListener('node_current', function(e) {
    var d = JSON.parse(e.data);
    markGraphNodeCurrent(d.node);
    
    // Re3.9.3: 搜索后 Human Gate
    if (d.node === 'human_gate_search') {
        showHumanGateSearch();
    }
});

function showHumanGateSearch() {
    var html = '<div id="gateSearchPanel" style="background:#fef3c7;border-radius:8px;padding:16px;margin:10px 0;text-align:center;">';
    html += '<div style="font-size:14px;font-weight:600;color:#92400e;margin-bottom:8px;">🔍 搜索阶段完成</div>';
    html += '<div style="font-size:12px;color:#78350f;margin-bottom:12px;">请确认搜索结果是否满意，然后继续分析阶段</div>';
    html += '<button onclick="confirmGateSearch()" style="padding:8px 24px;background:#2563eb;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:14px;">✓ 确认继续分析</button>';
    html += '</div>';
    document.getElementById('gateSearchContainer').innerHTML = html;
}

function confirmGateSearch() {
    // 调用 API 恢复 graph 执行
    fetch('/api/v1/research/' + currentCaseId + '/resume', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({'decision': 'continue'})
    }).then(function(r) { return r.json(); }).then(function(d) {
        document.getElementById('gateSearchContainer').innerHTML = '';
        document.getElementById('statusBar').textContent = '分析中...';
    });
}
```

HTML 中添加容器：
```html
<div id="gateSearchContainer"></div>
```

#### Fix 3.4: Resume API 端点

**文件**：`apps/api/app/api/v1/research.py`

```python
@router.post("/{case_id}/resume")
def resume_case(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Resume a paused graph (after human gate)."""
    decision = payload.get("decision", "continue")

    # 在后台线程中恢复 graph 执行
    import threading
    def _resume():
        try:
            from apps.api.app.services.agents.graph import research_graph as rg
            g = rg.build_graph()
            g.invoke(
                None,  # Resume from checkpoint
                config={
                    "configurable": {"thread_id": case_id},
                    "recursion_limit": 100,
                },
            )
            # 后续逻辑同 _run_case_sync 的落盘部分
            # ...
        except Exception as exc:
            with _LOCK:
                _RUN_STATUS[case_id] = {
                    "status": "error",
                    "error": type(exc).__name__,
                    "message": str(exc)[:500],
                }

    thread = threading.Thread(target=_resume, daemon=True)
    thread.start()

    return {"case_id": case_id, "status": "resuming"}
```

**注意**：LangGraph 的 `interrupt()` 需要 checkpointer 支持 resume。当前 `MemorySaver` 是内存检查点，server 重启会丢失。生产环境应换 SqliteSaver。但本次验证用 MemorySaver 即可。

#### Fix 3.5: _run_case_sync 支持中断恢复

需要重构 `_run_case_sync`，将 graph 执行分为两个阶段：

```python
# Phase 1: intake → ... → human_gate_search (interrupt)
# Phase 2: work_package → ... → final (resume)

# _run_case_sync 中使用 g.stream()，当遇到 interrupt 时:
# - 保存当前 trace
# - 设置 _RUN_STATUS["status"] = "paused"
# - 等待 /resume API 调用

# /resume 端点中调用 g.invoke(None, config=...) 从 checkpoint 恢复
```

**简化方案**：如果 `HUMAN_GATE_ENABLED=false`（调试模式），gate 直接 pass through，不需要 interrupt/resume 机制。本次验证可以先用调试模式跑通，gate 节点显示"pass_through"即可。启用模式留到后续。

### Phase 3 简化版（调试模式优先）

如果 interrupt/resume 太复杂，先实现"调试模式"：
- `HUMAN_GATE_ENABLED=false`（默认）
- gate 节点 pass_through，但在前端**显示一个短暂提示**（2 秒后自动消失）：
  "搜索完成，即将开始分析..."

```javascript
function showHumanGateSearch() {
    var html = '<div style="background:#fef3c7;border-radius:8px;padding:12px;margin:10px 0;text-align:center;">';
    html += '<span style="font-size:13px;color:#92400e;">🔍 搜索阶段完成，自动继续分析（调试模式）</span>';
    html += '</div>';
    var container = document.getElementById('gateSearchContainer');
    container.innerHTML = html;
    setTimeout(function() { container.innerHTML = ''; }, 3000);
}
```

## 3. 验证 (30min)

### 验证 case

| Case | 题目 | 验证重点 |
|---|---|---|
| R39-UI | 基于yolo的农作物识别 | 快速 case，观察实时论文 + graph 图 + gate |

### 验收标准

| # | 条件 | 通过标准 | 优先级 |
|---|---|---|---|
| 1 | 搜索期间论文逐步出现 | 截图显示蓝色 ⏳ 卡片 | P0 |
| 2 | Graph 图显示节点拓扑 | SVG 可见 | P0 |
| 3 | 当前执行节点高亮蓝色 | 截图 | P0 |
| 4 | 完成节点变绿 | 截图 | P0 |
| 5 | 搜索后显示 gate 提示 | 截图 | P0 |
| 6 | graph 完成无报错 | state.json | P0 |
| 7 | F12 Console 无红色 | 截图 | P0 |
| 8 | 论文最终替换为验证结果（绿/橙） | 截图 | P1 |
| 9 | 5 张截图 | 文件检查 | P1 |

### 截图清单

| # | 截图 | 内容 |
|---|---|---|
| 1 | 01_papers_streaming | 搜索中，论文逐步出现（蓝色 ⏳） |
| 2 | 02_graph_topology | Graph SVG 全貌 |
| 3 | 03_graph_current | 当前节点蓝色高亮 |
| 4 | 04_gate_search | 搜索后 gate 提示 |
| 5 | 05_final_complete | 全部完成（节点全绿 + 论文验证结果） |

## 4. 执行者规则

1. **Phase 1 先做**——实时论文推送是用户体验改善最大的
2. **Phase 2 可与 Phase 1 并行**——不同代码区域
3. **Phase 3 调试模式优先**——gate 用 pass_through，interrupt/resume 留后续
4. **只需 1 个 case 验证**
5. **commit per phase**

### Commit 规范

| Phase | Commit message |
|---|---|
| 1 | `feat(re3.9.3-phase1): 实时论文推送 — search_agent每步落盘+SSE papers_update+前端实时渲染` |
| 2 | `feat(re3.9.3-phase2): Graph图可视化 — SVG拓扑+节点高亮+点击跳转时间线` |
| 3 | `feat(re3.9.3-phase3): 搜索后HumanGate — human_gate_search节点+前端提示+resume API` |

## 5. 交付物

### 代码
| 文件 | 改动类型 | Phase |
|---|---|---|
| `search_agent.py` | 🔧 中间结果落盘 + 去重移入循环 | 1 |
| `research.py` | 🔧 SSE papers_update + graph-topology 端点 + resume 端点 | 1+2+3 |
| `index.html` | 🔧 papers_update 事件 + SVG graph + gate UI | 1+2+3 |
| `content.py` | 🆕 human_gate_search_node | 3 |
| `nodes/__init__.py` | 🔧 注册 human_gate_search | 3 |
| `research_graph.py` | 🔧 feasibility→gate→work_package | 3 |

### 数据
| 文件 | 内容 |
|---|---|
| `tmp_re39_eval/R39-UI/` | 验证 case |
| `tmp_re39_eval/screenshots/01-05_*.png` | 5 张截图 |

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| state_partial.json 频繁写入 | 低 | 磁盘 I/O | 每步 1 次 JSON 写入，~8 次，可忽略 |
| SVG graph 性能 | 低 | 渲染慢 | 节点数固定 23，SVG 性能足够 |
| interrupt/resume 不支持 MemorySaver | 中 | gate 无法暂停 | 调试模式 pass_through，不需要 resume |
| 前端事件顺序错乱 | 低 | UI 闪烁 | SSE 事件有顺序保证 |
