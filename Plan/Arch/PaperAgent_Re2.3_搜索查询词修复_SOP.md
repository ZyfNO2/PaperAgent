# PaperAgent Re2.3 搜索查询词修复与 Reflexion 修复 SOP

> 承接：Re2.2-fix 完工（5 个 fix 已 commit，代码正确但验证受限）
> **本 SOP 设计为全程无人值守执行。**
> 预计总时长：3-4 小时。
> 模型：DeepSeek (主)。

## 0. 问题总结

Re2.2-fix 代码修复正确，但 3-case 验证中 repos=0。根因不是代码 bug，而是**两层问题叠加**：

### 层 1：搜索查询词不精确

```
search_planner 给各适配器的查询词:
  openalex: "deep learning visual SLAM"  ← 正确（method+object 组合）
  crossref: "deep learning visual SLAM"  ← 正确（已改）
  arxiv:   "deep learning visual SLAM semantic mapping"  ← 正确（已改）
  github:  "deep learning"               ← 错误！只传了 method[0]，没拼 object
  retrieve._run_direct_adapter_retrieval 也有类似问题
```

同时 OpenAlex 全程 429 返回 0 结果，Crossref 和 GitHub 成了主要数据源。但：
- Crossref 只取 queries[0]（1 条查询），返回结果质量参差不齐
- GitHub 也只取 queries[0]（"deep learning"），返回的是 keras/annotated_deep_learning 等通用 repo

### 层 2：reflexion 机制失效（核心问题）

系统有 repair loop（`quality_gate → targeted_repair → retrieve`），但有三个盲区导致它在 OpenAlex 429 时形同虚设：

**盲区 A：quality_gate 触发阈值太低**

```python
# 当前: n_papers < 1 才触发 repair
# 但 weak_promote 把 weak_reject 提升后, n_papers >= 1 → 不触发 repair
```

OpenAlex 429 → 0 篇 → Crossref 8 篇垃圾 → verify 全部 weak_reject → quality_gate 提升到 10 篇 → `n_papers=10 ≥ 1` → **不触发 repair**。系统拿着 10 篇不相关论文继续跑。

**盲区 B：targeted_repair 不知道哪个适配器挂了**

```python
# 当前: _decide_repair_type 只看"缺什么类型" (baseline/dataset/repo/paper)
# 不看"为什么缺" → 不知道 OpenAlex 429 返回了 0
```

它生成新查询词回到 retrieve，但 OpenAlex 仍然 429，新查询词给 OpenAlex 还是返回 0。

**盲区 C：retrieve 没有 adapter 级别感知**

```python
# 当前: OpenAlex 429 → logger.warning + return tool, []
# 不重试, 不补偿其他适配器, 不传递"OpenAlex 挂了"给 quality_gate
```

### 完整失败链条

```
retrieve: OpenAlex 429 → 0 篇, Crossref 8 篇垃圾, GitHub 8 个通用 repo
    ↓
quality_filter: 过滤掉部分垃圾, 保留 ~15 篇
    ↓
verify: 全部 weak_reject (不相关), 0 accept
    ↓
quality_gate: weak_promote 10 篇 → n_papers=10 ≥ 1 → 不触发 repair → citation_expander
    ↓
citation_expander: 从 10 篇不相关论文中选种子 → 扩展出更多不相关论文
    ↓
最终: verified_papers 全是 weak_reject, feasibility=not_recommended, review=BLOCK
```

### 五个子问题

| # | 问题 | 位置 | 影响 |
|---|---|---|---|
| 1 | GitHub 查询词不精确 | retrieve.py `_run_direct_adapter_retrieval` 用 `method[0]` 搜 GitHub | 返回通用 repo，verify 正确拒绝 |
| 2 | Crossref/GitHub 只取 queries[0] | crossref_search.py 和 github_search.py 都 `qs = queries[:1]` | 只搜 1 条查询，浪费了 search_planner 生成的多条查询 |
| 3 | OpenAlex 429 无降级 | retrieve.py 不处理 OpenAlex 空结果 | OpenAlex 返回 0 时不增加其他适配器的 top_k |
| 4 | quality_gate 不看 accept rate | quality_gate.py 只看 n_papers < 1 | 0 accept 但有 weak_reject 时不触发 repair |
| 5 | targeted_repair 不感知适配器状态 | targeted_repair.py 不知道哪个适配器返回了 0 | repair 轮次重复跑挂掉的适配器 |

## 1. 修复计划

### Fix 1: retrieve.py — GitHub 查询词用 method+object 组合

**文件**：`apps/api/app/services/agents/graph/nodes/retrieve.py`

**当前代码**（`_run_direct_adapter_retrieral` 中构建 queries）：

```python
head = (method[:2] + obj[:2]) or [topic.split()[0] if topic else "deep learning"]
queries = []
for h in head:
    queries.append(f"{h}")
for d in ds_terms[:2]:
    queries.append(f"{d} dataset benchmark")
queries = [q for q in dict.fromkeys(queries).keys() if len(q) > 5][:6]
```

这里 `head` 已经是 `method[:2] + obj[:2]` 的组合，所以 queries 里已经有 `"deep learning"` 和 `"visual SLAM"` 两条。问题是 GitHub 和 Crossref 只取 `queries[0]`（可能是 "deep learning" 也可能是 "visual SLAM"）。

**修复**：不为 retrieve.py 改查询词构建逻辑（已经是对的），而是让 GitHub 和 Crossref 适配器**搜索所有 queries** 而非只搜 queries[0]。

### Fix 2: crossref_search.py — 搜索全部 queries（不只 queries[0]）

**文件**：`apps/api/app/services/retrieval/adapters/crossref_search.py`

**当前代码**：

```python
qs = [q for q in (queries or []) if q and q.strip()][:1]  # 只取第 1 条
```

**改为**：

```python
qs = [q for q in (queries or []) if q and q.strip()][:3]  # 取前 3 条
```

这样 Crossref 会搜 3 条查询（如 "deep learning" + "visual SLAM" + "semantic mapping dataset benchmark"），每条返回 8 篇，总共最多 24 篇。去重后预计 15-20 篇候选。

### Fix 3: github_search.py — 搜索全部 queries + 用 method+object 查询

**文件**：`apps/api/app/services/retrieval/adapters/github_search.py`

**当前代码**：

```python
qs = queries[:1] if queries else []  # 只取第 1 条
```

**改为**：

```python
qs = queries[:3] if queries else []  # 取前 3 条
```

这样 GitHub 会搜 3 条查询。对于 SLAM case，queries 会包含 "deep learning"、"visual SLAM"、"semantic mapping"——GitHub 搜 "visual SLAM" 会返回 openvslam/ORB_SLAM3 等真正的 SLAM repo。

### Fix 4: retrieve.py — OpenAlex 空结果时增加其他适配器 top_k

**文件**：`apps/api/app/services/agents/graph/nodes/retrieve.py`

**当前代码**：所有适配器用相同的 `top_k=8`。

**改为**：如果 OpenAlex 返回 0 结果（429 或空），给 Crossref 和 arxiv 的 top_k 增加到 12。

```python
# 在 _fetch_one 中
async def _fetch_one(tool: str) -> tuple[str, list[dict[str, Any]]]:
    try:
        async with semaphore:
            # 如果 OpenAlex 已经返回空，给其他适配器增加 top_k
            tool_top_k = 8
            if tool in ("crossref", "arxiv") and "openalex" in raw and not raw.get("openalex"):
                tool_top_k = 12
            hits = await REGISTRY[tool](queries, tool_top_k)
        return tool, hits or []
    except BaseException as exc:
        logger.warning("direct adapter %s failed: %s", tool, type(exc).__name__)
        return tool, []
```

注意：`raw` 在 `asyncio.gather` 时还没构建完，需要改成先跑 OpenAlex 再跑其他，或者用不同的策略。

**更简方案**：直接把所有适配器的 top_k 从 8 改为 12。OpenAlex 429 时返回 0 不影响，其他适配器多搜 4 篇。

```python
# 旧：
hits = await REGISTRY[tool](queries, 8)

# 新：
hits = await REGISTRY[tool](queries, 12)
```

### Fix 5: quality_gate.py — 0 accept 时触发 repair（reflexion 盲区 A）

**文件**：`apps/api/app/services/agents/graph/nodes/quality_gate.py`

**问题**：当前 `n_papers < 1` 才触发 repair。weak_promote 后 n_papers ≥ 1 就不修了。但 0 accept 说明搜索结果全不相关，应该 repair。

**修改**：在现有 `n_papers < 1` 检查后，增加 accept rate 检查：

```python
# 现有代码之后追加
n_accept = len([p for p in (state.get("verified_papers") or [])
                if (p.get("verdict") or "") == "accept"])
n_total = len(state.get("verified_papers") or []) + len(weak_papers)
accept_rate = n_accept / max(n_total, 1)

# 0 accept 但有候选论文 → 搜索有结果但都不相关 → repair 查询词
if (n_accept == 0 and n_total >= 3 and repair_rounds < max_repair
        and not citation_done):
    route = "repair"
```

**注意**：这个检查要在 weak_promote **之前**做。如果先 promote 了，verified_papers 里全是 weak_reject，accept 还是 0，但 n_papers 已经 ≥ 1 了。应该先判断"0 accept + 有候选 → repair"，再决定是否 promote。

调整 quality_gate 逻辑顺序：

```python
# 1. 先统计原始 accept 数（promote 前）
n_accept_original = len([p for p in (state.get("verified_papers") or [])
                         if (p.get("verdict") or "") == "accept"])
n_total = len(state.get("verified_papers") or []) + len(weak_papers)

# 2. 0 accept + 有候选 → repair（不 promote）
if (n_accept_original == 0 and n_total >= 3 and repair_rounds < max_repair
        and not citation_done):
    route = "repair"
    # 不 promote，直接走 repair
elif n_papers < 1 and repair_rounds < max_repair and not citation_done:
    route = "repair"
elif not citation_done and n_papers >= 1:
    # 有 accept 才 promote weak 和走 citation_expander
    route = "citation_expander"
else:
    route = "continue"
```

#### 3-case 验证

| 检查项 | 通过标准 |
|---|---|
| V-CRACK（Re2.2 0 accept）触发 repair | trace 有 targeted_repair 事件 |
| V-MED（有 accept）不触发额外 repair | trace 不比 Re2.2 多 repair |
| graph 完成 | ≥2/3 |

### Fix 6: retrieve.py + targeted_repair.py — 适配器级别感知（reflexion 盲区 B+C）

**文件 1**：`apps/api/app/services/agents/graph/nodes/retrieve.py`

**问题**：retrieve 不暴露 per-adapter 结果数，不跳过失败适配器。

**修改**：在 trace 的 output_summary 中增加 per-adapter 计数和失败列表：

```python
# 在构建 trace 时
trace["output_summary"]["per_adapter"] = {
    tool: len(hits) for tool, hits in raw.items()
}
trace["output_summary"]["failed_adapters"] = [
    tool for tool in tool_order if tool not in raw or not raw[tool]
]
```

repair 轮次中跳过上一轮失败的适配器：

```python
# 在 _run_direct_adapter_retrieval 开头
repair_rounds = state.get("evidence_audit", {}).get("repair_rounds", 0)
if repair_rounds > 0:
    # 从 trace 中读取上一轮失败的适配器
    traces = state.get("trace_events") or []
    retrieve_traces = [t for t in traces if t.get("node") in ("retrieve", "paper_retriever")]
    if retrieve_traces:
        last_failed = retrieve_traces[-1].get("output_summary", {}).get("failed_adapters", [])
        # 跳过上一轮返回 0 的适配器
        tool_order = [t for t in tool_order if t not in last_failed]
        logger.info("repair round %d: skipping failed adapters %s", repair_rounds, last_failed)
```

**文件 2**：`apps/api/app/services/agents/graph/nodes/targeted_repair.py`

**问题**：targeted_repair 不知道哪个适配器挂了。

**修改**：在 gaps 中传入 per-adapter 结果：

```python
# 在 targeted_repair_node 中构建 gaps 时
traces = state.get("trace_events") or []
retrieve_traces = [t for t in traces if t.get("node") in ("retrieve", "paper_retriever")]
if retrieve_traces:
    last_summary = retrieve_traces[-1].get("output_summary", {})
    gaps["per_adapter"] = last_summary.get("per_adapter", {})
    gaps["failed_adapters"] = last_summary.get("failed_adapters", [])
```

在 prompt 的 `P.build()` 中传入适配器信息（如果 `re12_repair.py` 的 build 函数支持额外参数，否则追加到 gaps dict 中由 LLM 读取）。

#### 3-case 验证

| 检查项 | 通过标准 |
|---|---|
| retrieve trace 有 per_adapter 字段 | ≥2/3 case |
| repair 轮次跳过失败的适配器 | V-CRACK repair 轮次的 retrieve trace 不含 openalex |
| graph 完成 | ≥2/3 |

| Case | 题目 | 领域 | 预期改善 |
|---|---|---|---|
| V-SLAM | 基于深度学习的视觉SLAM语义地图的研究 | SLAM | GitHub 搜 "visual SLAM" → 有 SLAM repo；Crossref 搜 3 条 → 更多候选 |
| V-CRACK | 基于深度学习的混凝土桥梁裂缝检测研究 | 土木 | Crossref 搜 "deep learning" + "concrete bridge" + "crack detection" → 更多相关论文 |
| V-MED | 基于大语言模型的医学问答可信度评估方法研究 | NLP/医学 | 验证不退化（已有 accept 的 case 不应变差） |

## 3. 验证通过标准

| 检查项 | 通过标准 |
|---|---|
| paper_candidates ≥ Re2.2-fix 同 case 的 1.3x | ≥2/3 case |
| V-SLAM 的 GitHub 结果包含 SLAM 相关 repo | V-SLAM 的 raw_results.github 中有 "slam" 标题 |
| graph 完成 | ≥2/3 has_final=True |
| 无退化 | V-MED 的 accept 数不比 Re2.2-fix 减少 |

## 4. 执行顺序

```
Fix 2 (crossref 多查询) + Fix 3 (github 多查询) → 验证 3 case → 通过则 Fix 4
                                        ↓
Fix 4 (top_k 增加) → 验证 3 case → 通过则 Fix 5
                                        ↓
Fix 5 (quality_gate accept rate) → 验证 3 case → 通过则 Fix 6
                                        ↓
Fix 6 (retrieve per-adapter + targeted_repair 感知) → 验证 3 case → 完成
```

Fix 2 和 Fix 3 可以同时改（不同文件且改动极小），然后一起验证。

Fix 5 和 Fix 6 有依赖关系：Fix 6 的 targeted_repair 读取 Fix 5 的 quality_gate 产生的 repair 信号。必须先 Fix 5 再 Fix 6。

## 5. 改动隔离

每次改代码前 `git stash create`。
验证通过记录 `tmp_re23_eval/changelog.md`。
验证失败 `git checkout` 回滚。

## 6. 禁止事项

- 禁止同时改多个文件（Fix 2+3 例外，因为是不同文件且改动极小）。
- 禁止改完代码不跑 3-case 验证。
- 禁止验证失败不回滚。
- 禁止用 VOAPI / MiniMax。
- 禁止用 mock 数据。

## 7. 交付物

代码：

- `apps/api/app/services/retrieval/adapters/crossref_search.py` 🔧 (Fix 2: queries[:1] → queries[:3])
- `apps/api/app/services/retrieval/adapters/github_search.py` 🔧 (Fix 3: queries[:1] → queries[:3])
- `apps/api/app/services/agents/graph/nodes/retrieve.py` 🔧 (Fix 4: top_k 8→12 + Fix 6: per-adapter 感知)
- `apps/api/app/services/agents/graph/nodes/quality_gate.py` 🔧 (Fix 5: 0 accept 触发 repair)
- `apps/api/app/services/agents/graph/nodes/targeted_repair.py` 🔧 (Fix 6: 传入适配器状态)

数据：

- `tmp_re23_eval/verify/` (3-case 验证结果)
- `tmp_re23_eval/changelog.md`

报告：

- `Plan/PaperAgent_Re2.3_完工报告.md`

## 8. 最终验收条件

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | Crossref 搜索 ≥2 条查询 | trace tool_calls 有 crossref count > 8 |
| 2 | GitHub 搜索 ≥2 条查询 | trace tool_calls 有 github count > 8 |
| 3 | paper_candidates ≥1.3x | ≥2/3 验证 case |
| 4 | V-SLAM GitHub 有 SLAM repo | raw_results.github 有 "slam" 标题 |
| 5 | V-MED 不退化 | V-MED accept ≥ Re2.2-fix |
| 6 | 0 accept 时触发 repair | V-CRACK trace 有 targeted_repair 事件 |
| 7 | repair 轮次跳过失败适配器 | repair retrieve trace 不含 openalex |
| 8 | retrieve trace 有 per_adapter | ≥2/3 case |
| 9 | graph 完成 | ≥2/3 |
| 10 | changelog 记录 | 文件检查 |
| 11 | VOAPI/MiniMax = 0 | 全程 |
