# PaperAgent Re3.0 多步工具调用可观测性 SOP（草稿）

> 状态：**草稿，待排期。** 当前阶段不执行。
> 预计排期：Re2.4 完成后，视实际多步调用的痛点严重程度决定是否启动。
> 预计总时长：6-10 小时。

## 0. 问题背景

当前系统（Re2.x）的 graph 是 20+ 节点的线性/条件边链路，每个节点内部是单次 LLM 调用 + 规则处理。可观测性靠 trace_events（每节点记 started_at/ended_at/elapsed_s）和 SSE 推送。

Re3.0 要做的是**多步工具调用的调度 Agent**——不再是固定 graph 链路，而是 LLM 自主决定调用哪个工具、观察结果、再决定下一步。这会引入：

1. **思考→调用→观察循环**：LLM 在一个节点内多次调用工具（arxiv → 看结果 → crossref → 看结果 → s2 → 看结果 → 决定够了），循环次数不确定。
2. **上下文超限**：每次工具调用的返回结果都追加到 LLM 上下文，多步后 token 超限。
3. **工具被截断**：LLM 输出的 tool_call JSON 可能被 max_tokens 截断，导致工具名/参数不完整。
4. **日志散乱**：多步循环中，LLM 思考、工具调用、工具返回交织在一起，时间线错位。
5. **LangSmith trace 不足**：LangSmith 能看到每次 LLM 调用，但多步思维链的 parent-child 关系不清晰，需要手动标记 parent_id。
6. **召回率不可观测**：工具调用的"召回率"（搜索结果是否相关）没有 metric，只能肉眼判断。

## 1. 本轮目标

为多步工具调用建立**可观测性基础设施**，让调度 Agent 的每一步都可追踪、可度量、可调试。

必须完成：

1. **结构化 trace**：每次工具调用记录 parent_id / step_idx / tool_name / input / output / elapsed / token_count，不再散乱。
2. **上下文管理**：多步循环中自动压缩历史工具结果，防止 token 超限。
3. **工具截断检测**：LLM 输出的 tool_call 被截断时自动检测 + 重试 + 告警。
4. **LangSmith 集成**：多步思维链的 parent-child 关系自动标记，trace 可视化时间线不错位。
5. **自定义 metric**：工具召回率（搜索结果相关性）、工具成功率、平均步数、token 消耗。
6. **实时仪表盘**：前端显示当前调度 Agent 的思考→调用→观察循环状态。

不做：

- 改变现有 20 节点 graph 架构（Re3.0 只增加可观测性，不改 graph 拓扑）。
- 新增分析节点（feasibility/innovation 等不变）。
- 部署 / Docker。

## 2. 技术方案

### 2.1 结构化 trace

当前 trace_events 是扁平的节点列表。Re3.0 需要支持**嵌套 trace**——一个节点内部的多步工具调用：

```python
# 当前
trace_events = [
    {"node": "retrieve", "elapsed_s": 20.5, "tool_calls": [{"tool": "arxiv", "n": 8}]},
]

# Re3.0
trace_events = [
    {
        "node": "retrieve_agent",
        "trace_id": "tr_001",
        "parent_trace_id": None,
        "started_at": "...",
        "ended_at": "...",
        "elapsed_s": 45.2,
        "steps": [
            {
                "step_idx": 0,
                "trace_id": "tr_001_step_0",
                "parent_trace_id": "tr_001",
                "type": "thought",          # thought / tool_call / observation
                "content": "I need to search for SLAM papers. Let me try arxiv first.",
                "started_at": "...",
                "elapsed_s": 2.1,
                "token_count": {"prompt": 150, "completion": 30},
            },
            {
                "step_idx": 1,
                "trace_id": "tr_001_step_1",
                "parent_trace_id": "tr_001",
                "type": "tool_call",
                "tool": "arxiv",
                "input": {"query": "visual SLAM semantic mapping", "top_k": 8},
                "started_at": "...",
                "ended_at": "...",
                "elapsed_s": 3.2,
            },
            {
                "step_idx": 2,
                "trace_id": "tr_001_step_2",
                "parent_trace_id": "tr_001",
                "type": "observation",
                "tool": "arxiv",
                "output": {"n_results": 8, "titles": ["DS-SLAM", "VAR-SLAM", ...]},
                "relevance_score": 0.75,    # 自定义 metric
                "started_at": "...",
                "elapsed_at": "...",
                "elapsed_s": 0.1,
            },
            {
                "step_idx": 3,
                "trace_id": "tr_001_step_3",
                "parent_trace_id": "tr_001",
                "type": "thought",
                "content": "arxiv returned 8 SLAM papers. Let me also check GitHub for repos.",
                "started_at": "...",
                "elapsed_s": 1.8,
                "token_count": {"prompt": 200, "completion": 25},
            },
            # ... 更多步骤
        ],
        "total_steps": 7,
        "total_tokens": {"prompt": 1200, "completion": 180},
        "tools_used": ["arxiv", "github", "crossref"],
        "context_truncated": False,        # 是否发生了上下文压缩
    },
]
```

### 2.2 上下文管理

多步循环中，每次工具返回的结果追加到 LLM 上下文。如果不管理，5 步后 token 可能超限。

**策略：滑动窗口 + 摘要压缩**

```python
class ContextManager:
    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self.messages: list[dict] = []
        self.estimated_tokens: int = 0
    
    def add_tool_result(self, tool: str, result: dict):
        """添加工具结果，超限时自动压缩旧结果。"""
        result_str = json.dumps(result, ensure_ascii=False)
        result_tokens = estimate_tokens(result_str)
        
        # 如果加入后超限，压缩旧的工具结果
        while self.estimated_tokens + result_tokens > self.max_tokens and len(self.messages) > 2:
            # 找到最早的工具结果，压缩为摘要
            for i, msg in enumerate(self.messages):
                if msg.get("role") == "tool":
                    old_result = msg["content"]
                    summary = self._summarize(old_result)
                    self.messages[i] = {
                        "role": "tool",
                        "content": f"[compressed] {summary}",
                        "_compressed": True,
                    }
                    self.estimated_tokens -= (estimate_tokens(old_result) - estimate_tokens(summary))
                    break
        
        self.messages.append({"role": "tool", "content": result_str, "tool": tool})
        self.estimated_tokens += result_tokens
    
    def _summarize(self, text: str) -> str:
        """用 LLM 压缩工具结果为摘要。"""
        # 简单方案：只保留前 200 字符 + "..."
        if len(text) > 200:
            return text[:200] + "... [compressed]"
        return text
```

### 2.3 工具截断检测

LLM 输出的 tool_call JSON 可能被 max_tokens 截断：

```python
def parse_tool_call(raw_output: str) -> dict | None:
    """解析 LLM 输出的 tool_call，检测截断。"""
    try:
        parsed = json.loads(raw_output)
        # 验证必要字段
        if "tool" not in parsed:
            raise ValueError("missing 'tool' field")
        if "input" not in parsed:
            raise ValueError("missing 'input' field")
        return parsed
    except json.JSONDecodeError as e:
        # JSON 不完整 → 可能被截断
        logger.warning("tool_call JSON parse failed: %s. Output may be truncated.", e)
        logger.debug("raw output (last 100 chars): ...%s", raw_output[-100:])
        
        # 尝试修复：补全 JSON
        fixed = try_repair_json(raw_output)
        if fixed:
            logger.info("tool_call JSON repaired successfully")
            return fixed
        
        # 修复失败 → 告警 + 返回 None
        logger.error("tool_call truncated and unrepairable. Raw length=%d", len(raw_output))
        return None
```

### 2.4 LangSmith 集成

LangSmith 的 trace 默认按 LLM 调用平铺。多步思维链需要 parent-child 关系：

```python
from langsmith import traceable

@traceable(name="retrieve_agent", run_type="chain")
def retrieve_agent(topic: str, atoms: dict):
    """多步工具调用的检索 Agent。"""
    context = ContextManager(max_tokens=8000)
    steps = []
    
    for step_idx in range(MAX_STEPS):
        # 1. 思考：LLM 决定下一步
        thought = llm_think(topic, atoms, context.messages)
        steps.append({"step_idx": step_idx, "type": "thought", "content": thought})
        
        # 2. 如果 LLM 决定停止 → 退出
        if thought.get("stop"):
            break
        
        # 3. 工具调用
        tool_name = thought["tool"]
        tool_input = thought["input"]
        
        # LangSmith 自动追踪子 run
        result = call_tool_with_trace(tool_name, tool_input)
        
        # 4. 观察
        context.add_tool_result(tool_name, result)
        relevance = compute_relevance(result, topic, atoms)
        steps.append({
            "step_idx": step_idx,
            "type": "tool_call",
            "tool": tool_name,
            "input": tool_input,
            "output_summary": {"n": len(result), "relevance": relevance},
        })
    
    return {"steps": steps, "total_steps": len(steps)}
```

### 2.5 自定义 metric

```python
# 工具召回率：搜索结果与题目的相关性
def compute_relevance(results: list[dict], topic: str, atoms: dict) -> float:
    """计算搜索结果的相关性分数 (0-1)。"""
    if not results:
        return 0.0
    topic_kw = set()
    for key in ("method", "object", "task"):
        for v in (atoms.get(key) or []):
            topic_kw.add(str(v).lower())
    
    relevant = 0
    for r in results:
        title = (r.get("title") or "").lower()
        if any(kw in title for kw in topic_kw):
            relevant += 1
    
    return relevant / len(results)

# 自定义 LangSmith metric
def tool_relevance_metric(run: dict, example: dict) -> dict:
    """LangSmith evaluator: 工具召回率。"""
    steps = run.outputs.get("steps", [])
    tool_calls = [s for s in steps if s["type"] == "tool_call"]
    
    scores = [s.get("output_summary", {}).get("relevance", 0) for s in tool_calls]
    avg_relevance = sum(scores) / len(scores) if scores else 0
    
    return {
        "key": "tool_relevance",
        "score": avg_relevance,
        "comment": f"avg relevance across {len(tool_calls)} tool calls",
    }
```

### 2.6 实时仪表盘

前端显示调度 Agent 的循环状态：

```
┌─ 调度 Agent ────────────────────────────────────────────┐
│                                                         │
│  Step 3/∞                                               │
│  ┌─ 思考 ─────────────────────────────────────────────┐ │
│  │ arxiv 返回 8 篇 SLAM 论文，但只有 2 篇有 repo。    │ │
│  │ 我需要搜 GitHub 找更多 repo。                      │ │
│  └────────────────────────────────────────────────────┘ │
│  ┌─ 工具调用 ─────────────────────────────────────────┐ │
│  │ 🔧 github_search("visual SLAM")                    │ │
│  │ ⏱ 0.8s                                             │ │
│  └────────────────────────────────────────────────────┘ │
│  ┌─ 观察 ─────────────────────────────────────────────┐ │
│  │ 📊 6 个 repo (openvslam, ORB_SLAM3, ...)           │ │
│  │ 📈 相关性: 0.83                                    │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  Token: 1,240 / 8,000 (15%)                            │
│  工具: arxiv ✅ github ✅ crossref ⏳                  │
│                                                         │
│  [思考中...] ████████░░░░░░░░                           │
└─────────────────────────────────────────────────────────┘
```

SSE 事件：

```python
# 每步推送
yield _sse_event("agent_step", {
    "step_idx": step_idx,
    "type": "thought",  # thought / tool_call / observation
    "content": "...",
    "tool": "github",
    "elapsed_s": 0.8,
    "token_count": 1240,
    "token_limit": 8000,
    "relevance": 0.83,
})
```

## 3. Phase 设计（草稿）

### Phase 1：结构化 trace 基础设施 (2h)

- 新增 `StepTrace` 数据结构（parent_id / step_idx / type / content / tool / elapsed / token_count）。
- 修改 `ResearchState` 新增 `agent_steps: list[StepTrace]` 字段。
- 修改 trace_events 支持嵌套 steps。

### Phase 2：上下文管理器 (1.5h)

- 新增 `ContextManager` 类（滑动窗口 + 摘要压缩）。
- 集成到调度 Agent 的循环中。
- 测试：模拟 10 步工具调用，确认 token 不超限。

### Phase 3：工具截断检测 (1h)

- 新增 `parse_tool_call()` + `try_repair_json()`。
- 截断时自动重试（增加 max_tokens 50%）。
- 截断时告警（trace 标记 `truncated=True`）。

### Phase 4：LangSmith 集成 (1.5h)

- 用 `@traceable` 装饰调度 Agent。
- 多步循环中每步创建子 run。
- 自定义 metric: tool_relevance / tool_success / avg_steps / total_tokens。
- 在 LangSmith UI 中验证 parent-child 时间线不错位。

### Phase 5：实时仪表盘 (2h)

- SSE 新增 `agent_step` 事件。
- 前端新增调度 Agent 面板（思考/工具调用/观察循环显示）。
- Token 使用量进度条。
- 工具状态指示器。

### Phase 6：验证 + 报告 (1h)

- 用 medical-LLM case 跑调度 Agent，验证 trace 结构正确。
- 验证 LangSmith trace 时间线不错位。
- 验证上下文不超限。
- 验证截断检测生效。
- 输出完工报告。

## 4. 交付物（草稿）

代码：

- `apps/api/app/services/agents/observability/step_trace.py` 🆕 (StepTrace 数据结构)
- `apps/api/app/services/agents/observability/context_manager.py` 🆕 (上下文管理)
- `apps/api/app/services/agents/observability/tool_parser.py` 🆕 (截断检测)
- `apps/api/app/services/agents/observability/metrics.py` 🆕 (自定义 metric)
- `apps/api/app/services/agents/observability/langsmith_integration.py` 🆕 (LangSmith 集成)
- `apps/api/app/api/v1/research.py` 🔧 (SSE agent_step 事件)
- `apps/web/index.html` 🔧 (调度 Agent 面板)
- `apps/api/app/services/agents/graph/state.py` 🔧 (agent_steps 字段)

测试：

- `apps/api/tests/test_re3_0_context_manager.py` 🆕
- `apps/api/tests/test_re3_0_tool_parser.py` 🆕
- `apps/api/tests/test_re3_0_step_trace.py` 🆕

报告：

- `Plan/PaperAgent_Re3.0_完工报告.md`

## 5. 前置条件

- Re2.4 完成（前端重做 + 状态机进度条）。
- LangSmith API key 已配置（`LANGSMITH_API_KEY`）。
- 调度 Agent 的设计已确定（哪些节点改为多步循环）。

## 6. 与当前架构的关系

Re3.0 **不改 graph 拓扑**，只增强可观测性。具体来说：

| 当前节点 | Re3.0 改动 |
|---|---|
| retrieve | 可选改为调度 Agent（多步工具调用） |
| verify | 不变 |
| citation_expander | 可选改为调度 Agent（多步 S2 API 调用） |
| 其他节点 | 不变 |

调度 Agent 是**可选增强**，不是必须的。如果 retrieve 的单次调用已经够用（Re2.3 修复后），就不需要改成多步循环。Re3.0 的可观测性基础设施可以先建好，等需要时再用。

## 7. 风险

1. **LangSmith 免费层限制**：LangSmith 免费层每月 5000 traces，多步循环可能快速消耗。
2. **上下文压缩质量**：简单截断可能丢失关键信息，LLM 摘要压缩增加延迟。
3. **截断修复不完美**：JSON 修复不总是成功，需要 fallback 策略。
4. **前端复杂度**：调度 Agent 面板增加前端复杂度，可能影响性能。

## 8. 备注

本 SOP 为草稿，排期待定。执行前需要：

1. 确认 LangSmith API key 可用。
2. 确认哪些节点需要改为调度 Agent。
3. 确认上下文管理的 max_tokens 阈值。
4. 评审结构化 trace 的 schema 是否满足需求。
