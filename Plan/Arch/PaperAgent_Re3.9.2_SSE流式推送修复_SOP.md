# PaperAgent Re3.9.2 SSE 流式推送修复 — g.stream() 替代 g.invoke() SOP

> 承接：Re3.9.1 PubMed 强制注入修复。实际使用中发现前端在 graph 执行期间"中途没有任何流式显示"——SSE 事件全部在 graph 跑完后一次性推送。
> **本 SOP 聚焦：用 LangGraph stream() 替代 invoke()，实现真正的逐节点流式推送**
> 预计总时长：2-3 小时，分 3 个 Phase。
> 模型：DeepSeek (主)，StepFun (fallback)。

## 0. 问题根因分析

### 当前流程（阻塞式）

```
前端: EventSource(/stream) ← 0.5s 轮询 trace.json
后端: g.invoke(state_in)   ← 阻塞，跑完所有节点才返回
      → trace.json 写入     ← 跑完后才写
      → SSE 检测到 trace.json 存在 → 一次性推送全部事件
```

**结果**：用户点击"开始研究"后，前端显示"搜索中..."然后干等 3-5 分钟，期间无任何进度更新，直到 graph 跑完突然全部变绿。

### 目标流程（流式）

```
前端: EventSource(/stream) ← 实时接收
后端: g.stream(state_in)   ← 每个节点完成后产出 chunk
      → 每个 chunk 实时写入 trace.json（追加）
      → SSE 检测到新 trace → 立即推送 node_complete
```

**结果**：用户看到每个节点逐步变绿，search_agent 完成后立即显示论文数量，无需等待整个 graph。

### 当前 SSE 代码分析

SSE 端点 (`research.py` L528-654) 已有正确的轮询逻辑：
- 每 0.5s 读取 trace.json
- 检测新事件 → 推送 `node_complete`
- 检测 `status == "done"` → 推送 `done`

**SSE 端不需要改**——问题在 `_run_case_sync` 用 `g.invoke()` 一次性跑完，trace.json 在跑完之后才写入。

### LangGraph stream() 行为

```python
# g.invoke() — 阻塞，返回最终 state
out = g.invoke(state_in, config={...})

# g.stream() — 生成器，每个节点完成后 yield 一个 dict
for chunk in g.stream(state_in, config={...}):
    # chunk = {node_name: {partial_state_patch}}
    # 可以实时拿到每个节点的返回值
```

`stream()` 支持 `stream_mode` 参数：
- `"values"` — 每步产出完整 state（内存占用大）
- `"updates"` — 每步产出 state patch（推荐，轻量）
- `"debug"` — 包含执行元数据

## 1. 本轮目标

1. **`_run_case_sync` 改用 `g.stream()`**——每个节点完成后立即追加 trace 事件到 trace.json
2. **SSE 轮询已支持增量推送**——不需要改 SSE 端点，只需后端中间落盘
3. **前端已有 `node_complete` 处理**——不需要改前端
4. **验证**——跑 1 个 case，确认前端逐节点变绿

不做：
- 重写 SSE 为 WebSocket（SSE 轮询够用）
- 重构前端（已有 node_complete 事件处理）
- 修改 graph 拓扑
- 修改 node 内部逻辑

## 2. Phase 设计

### Phase 1：_run_case_sync 改用 g.stream() (1.5h)

#### Fix 1.1: 替换 invoke 为 stream

**文件**：`apps/api/app/api/v1/research.py` L133-191

```python
def _run_case_sync(case_id: str, topic: str, extra: dict[str, Any]) -> None:
    """Synchronous wrapper for the research graph, executed in a thread."""
    t0 = time.time()
    cd = _case_dir(case_id)
    cd.mkdir(parents=True, exist_ok=True)

    # Re3.9.2: trace 文件预创建（空列表），SSE 轮询可以立即检测到文件存在
    trace_path = cd / "trace.json"
    trace_path.write_text("[]", encoding="utf-8")

    all_trace_events: list[dict[str, Any]] = []
    final_state: dict[str, Any] = {}

    try:
        from apps.api.app.services.agents.graph import research_graph as rg
        from apps.api.app.services.agents.graph.state import ResearchState

        state_in: ResearchState = {
            "case_id": case_id,
            "topic": topic,
            "user_constraints": extra.get("user_constraints",
                                          {"topic_zh": extra.get("title", "")}),
            "trace_events": [],
            "provider_profile": "fast_json",
            "errors": [],
        }
        user_papers = _USER_PAPERS.pop(case_id, None)
        if user_papers:
            state_in["user_papers"] = user_papers

        g = rg.build_graph()

        # Re3.9.2: 用 stream 替代 invoke，每个节点完成后实时落盘 trace
        for chunk in g.stream(
            state_in,
            config={
                "configurable": {"thread_id": case_id},
                "recursion_limit": 100,
            },
            stream_mode="updates",  # 只产出 state patch，轻量
        ):
            # chunk = {node_name: {state_patch}}
            for node_name, patch in chunk.items():
                if not isinstance(patch, dict):
                    continue

                # 收集 trace_events
                node_traces = patch.get("trace_events") or []
                for t in node_traces:
                    all_trace_events.append(t)

                # 实时追加写入 trace.json
                trace_path.write_text(
                    json.dumps(all_trace_events, ensure_ascii=False,
                               indent=2, default=str),
                    encoding="utf-8",
                )

                # 合并 patch 到 final_state
                final_state.update(patch)

        elapsed = round(time.time() - t0, 2)
        final_state["elapsed_s"] = elapsed
        final_state["trace_events"] = all_trace_events

        # 最终写入 state.json
        (cd / "state.json").write_text(
            json.dumps(final_state, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        # trace.json 已在上面实时写入，最终再写一次确保完整
        trace_path.write_text(
            json.dumps(all_trace_events, ensure_ascii=False,
                       indent=2, default=str),
            encoding="utf-8",
        )
        (cd / "evidence_graph.json").write_text(
            json.dumps(final_state.get("evidence_graph") or {},
                       ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        with _LOCK:
            _RUN_STATUS[case_id] = {
                "status": "done",
                "elapsed_s": elapsed,
                "n_papers": len(final_state.get("verified_papers") or []),
                "n_packages": len(final_state.get("work_packages") or []),
                "n_nodes": len(all_trace_events),
            }
    except Exception as exc:
        # 即使失败也保存已收集的 trace
        trace_path.write_text(
            json.dumps(all_trace_events, ensure_ascii=False,
                       indent=2, default=str),
            encoding="utf-8",
        )
        with _LOCK:
            _RUN_STATUS[case_id] = {
                "status": "error",
                "error": type(exc).__name__,
                "message": str(exc)[:500],
            }
```

#### 关键变更点

| 变更 | 说明 |
|---|---|
| `g.invoke()` → `g.stream(stream_mode="updates")` | 每个节点完成后 yield state patch |
| trace.json 预创建为 `[]` | SSE 轮询可以立即检测到文件存在（空列表），不报 404 |
| 每次收到 chunk 后追加写入 trace.json | SSE 0.5s 轮询能检测到新事件 |
| final_state 在循环中逐步合并 | 替代 invoke 的单次返回 |
| 异常处理中也写入 trace | 失败时保留已完成的 trace 事件 |

#### 注意事项

1. **`stream_mode="updates"` 返回的是 `{node_name: {patch}}` 格式**——不是完整 state，是节点的返回值（partial patch）
2. **LangGraph 的 state merge 语义**——`trace_events` 在 ResearchState 中如果是 `Annotated[list, operator.add]`，LangGraph 会自动追加；如果是普通 list，每个 node 返回的 `trace_events: [trace]` 会**覆盖**前一个。需要确认：
   - 如果是 `operator.add`：`all_trace_events` 可以直接从 `patch["trace_events"]` 收集
   - 如果是普通 list：需要从 final_state 中每次重新读取完整 trace_events
3. **checkpoint 兼容性**——`g.stream()` 和 `g.invoke()` 使用相同的 checkpointer，thread_id 一致即可恢复

#### Fix 1.2: 确认 ResearchState trace_events merge 行为

**文件**：`apps/api/app/services/agents/graph/state.py`

```bash
# 检查 trace_events 是否是 Annotated[list, operator.add]
grep "trace_events" apps/api/app/services/agents/graph/state.py
```

如果不是 `operator.add`，需要修改：

```python
# state.py:
from typing import Annotated
from operator import add

class ResearchState(TypedDict):
    ...
    trace_events: Annotated[list, add]  # 追加语义，不是覆盖
    ...
```

这样 LangGraph 内部会自动追加 trace_events，`g.stream()` 的 chunk 中 `patch["trace_events"]` 只包含当前节点的新事件。

### Phase 2：SSE 轮询优化 (30min)

#### Fix 2.1: SSE 轮询间隔缩短

**文件**：`apps/api/app/api/v1/research.py` L533

```python
# 修改前:
poll_interval = 0.5

# 修改后:
poll_interval = 0.3  # Re3.9.2: 更快的轮询，减少前端延迟
```

#### Fix 2.2: SSE 推送 node_current 事件（新增）

当前 SSE 只推送 `node_complete`——节点完成后才推送。为了在节点**开始执行**时就推送，可以利用 LangGraph stream 的 chunk 到达时机：

在 `_run_case_sync` 中，每个 chunk 到达时不仅写 trace.json，还可以更新 `_RUN_STATUS`：

```python
# 在 chunk 处理循环中:
with _LOCK:
    _RUN_STATUS[case_id] = {
        **_RUN_STATUS.get(case_id, {}),
        "status": "running",
        "current_node": node_name,  # Re3.9.2: 当前正在执行的节点
        "n_trace_events": len(all_trace_events),
    }
```

SSE 端点检测到 `current_node` 变化时推送 `node_current` 事件：

```python
# SSE event_generator 中:
# 检测 current_node 变化
current_node = _RUN_STATUS.get(case_id, {}).get("current_node", "")
if current_node and current_node != last_current_node:
    yield _sse_event("node_current", {"node": current_node})
    last_current_node = current_node
```

前端添加 `node_current` 事件处理：

```javascript
es.addEventListener('node_current', function(e) {
    var d = JSON.parse(e.data);
    markNodeCurrent(d.node);
});
```

**效果**：节点开始执行时前端立即标记为"当前"（蓝色），执行完成后标记为"完成"（绿色），而不是等全部跑完。

### Phase 3：验证 (1h)

#### 3.1 验证 case

跑 1 个 case，观察前端是否逐节点显示进度：

| Case | 题目 | 验证重点 |
|---|---|---|
| R39-STREAM | 基于yolo的农作物识别 | 快速 case（~300s），观察流式效果 |

#### 3.2 验证检查清单

**P0**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | graph 执行期间 trace.json 逐步增长 | 文件修改时间变化 |
| 2 | SSE 在 graph 执行期间推送 node_complete | 前端逐节点变绿 |
| 3 | 前端状态机 chip 逐个变色 | 不是全部一起变绿 |
| 4 | 前端"搜索中..."期间有进度更新 | 不是干等 |
| 5 | search_agent 完成后立即显示论文数量 | 候选面板更新 |
| 6 | graph 完成无 RecursionError | trace.json |
| 7 | verified_papers ≥ 3 | state.json |
| 8 | final_rec 计数匹配 | state.json |
| 9 | F12 Console 无红色错误 | 浏览器 |

**P1**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 10 | node_current 事件推送 | 前端标记"当前"节点 |
| 11 | trace.json 最终完整 | 事件数量 == 正常链路 |
| 12 | state.json 内容完整 | 与 invoke() 结果一致 |
| 13 | 异常时 trace 保留 | 模拟 LLM 失败，检查 trace.json 有部分事件 |

#### 3.3 截图

| # | 截图 | 内容 |
|---|---|---|
| 1 | 01_streaming_intake | intake 完成后前端显示（1 个绿 chip） |
| 2 | 02_streaming_search | search_agent 执行中（蓝色 retrieve chip） |
| 3 | 03_streaming_verify | verify 完成后（多个绿 chip + 论文数量更新） |
| 4 | 04_streaming_done | 全部完成（23/23 绿 + 完成耗时） |
| 5 | 05_console_clean | F12 Console 无红色 |

**保存路径**：`tmp_re39_eval/screenshots/`

## 3. 执行者规则

1. **Phase 1 是核心**——stream 替代 invoke 是架构级改动
2. **先确认 trace_events merge 行为**——决定 all_trace_events 收集方式
3. **每改一步跑 test_re1_2_graph_nodes**——确认 graph 仍能编译和执行
4. **Phase 2 在 Phase 1 完成后执行**——需要 stream 正常工作
5. **commit per phase**

### Commit 规范

| Phase | Commit message |
|---|---|
| 1 | `feat(re3.9.2-phase1): g.stream()替代g.invoke() — 逐节点实时落盘trace` |
| 2 | `feat(re3.9.2-phase2): SSE轮询优化 + node_current事件推送` |
| 3 | `test(re3.9.2-phase3): 流式推送验证 — 5张截图` |

## 4. 交付物

### 代码
| 文件 | 改动类型 | Phase |
|---|---|---|
| `apps/api/app/api/v1/research.py` | 🔧 _run_case_sync stream + SSE node_current | 1+2 |
| `apps/api/app/services/agents/graph/state.py` | 🔧 trace_events Annotated[list, add] | 1 |
| `apps/web/index.html` | 🔧 node_current 事件处理 | 2 |

### 数据
| 文件 | 内容 |
|---|---|
| `tmp_re39_eval/R39-STREAM/state.json` | 验证 case state |
| `tmp_re39_eval/R39-STREAM/trace.json` | 验证 case trace |
| `tmp_re39_eval/screenshots/01-05_*.png` | 5 张流式截图 |

### 报告
| 文件 | 内容 |
|---|---|
| `Plan/PaperAgent_Re3.9.2_完工报告.md` | 完工报告 |

## 5. 最终验收条件

| # | 条件 | 验证方式 | 优先级 |
|---|---|---|---|
| 1 | g.stream() 正常执行 | graph 完成无报错 | P0 |
| 2 | trace.json 在 graph 执行期间逐步增长 | 文件 mtime 变化 | P0 |
| 3 | SSE 在执行期间推送 node_complete | 前端逐节点变绿 | P0 |
| 4 | 前端状态机逐个变色 | 截图对比 | P0 |
| 5 | search_agent 完成后立即显示论文数 | 截图 | P0 |
| 6 | graph 完成无 RecursionError | trace.json | P0 |
| 7 | verified_papers ≥ 3 | state.json | P0 |
| 8 | final_rec 计数匹配 | state.json | P0 |
| 9 | F12 Console 无红色 | 截图 | P0 |
| 10 | node_current 事件推送 | 前端标记当前节点 | P1 |
| 11 | trace.json 最终完整 | 事件数量正确 | P1 |
| 12 | state.json 内容完整 | 与 invoke 结果一致 | P1 |
| 13 | 5 张截图 | 文件检查 | P1 |
| 14 | commit per phase | git log | P1 |

## 6. 执行顺序

```
Phase 1 (1.5h): g.stream() 替代 g.invoke() + trace.json 实时落盘
       ↓
Phase 2 (30min): SSE 轮询优化 + node_current 事件
       ↓
Phase 3 (1h):    验证 + 5 张截图
```

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| stream() 行为与 invoke() 不一致 | 中 | state 合并语义不同 | 先确认 trace_events 的 Annotated 类型 |
| trace_events 被 stream 覆盖而非追加 | 高 | trace 不完整 | 确认 state.py 中 Annotated[list, add] |
| stream() 不支持 checkpointer | 低 | 无法恢复 | LangGraph 文档确认 stream 支持 checkpointer |
| trace.json 频繁写入影响性能 | 低 | 磁盘 I/O | 每次 chunk 只写一次，~27 次 I/O，可忽略 |
| SSE 轮询读取到半写入的 JSON | 低 | JSON 解析失败 | 已有 try/except 处理 |
| final_state 不完整（stream patch 漏字段） | 中 | state.json 缺失字段 | 最终从 checkpointer 获取完整 state |
