# PaperAgent Re1.2 Loop 3 真实小样例 3

> SOP §14 Loop 3: 真实 3 样例。题目复用 Re1.1 Loop3 + Re1.2 SOP §8。

## 题目

1. `基于YOLOv5的钢铁表面缺陷检测研究` → "YOLOv5-based steel surface defect detection on hot-rolled strip using NEU-DET dataset"
2. `基于深度学习的视觉SLAM语义地图的研究` → "Deep learning-based visual SLAM semantic mapping for indoor environments"
3. `基于大语言模型的医学问答可信度评估方法研究` → "LLM-based medical question-answer credibility and factuality estimation"

## 验收标准

- 每个 case paper >= 3
- 每个 case 输出 evidence graph
- 至少 2/3 case 有 repo 或明确 repo repair
- 至少 2/3 case 有 dataset 或明确 dataset repair
- 每个 case 有 baseline/parallel 分类结果
- work_package 为空时必须给出具体缺口和 repair query

## 实际结果

### 开发期单候选验证

在 runner 完整跑之前, 先手工验证核心 fallback:

```
测试: 1 篇 candidate 'YOLOv5s-GTB: light-weighted YOLOv5 for bridge crack detection'
  → topic_atoms method=[YOLOv5] object=[steel] task=[defect detection]
  → re11_paper_verifier prompt (per-candidate) → call_json expected=any
```

**结果**: ✅

```
stepfun step-3.7-flash 第 1 次: content='{"":""}' reasoning='balanced scan failed'
→ _contains_json_object False → fallback 到 step-1v-32k
→ step-1v-32k content='{"title":"...","verdict":"weak_reject",...}'
→ call_json 解析 → list of 1 verdict
→ verify_node 输出: 0 accept, 1 weak_reject
```

注: 该 candidate 为 "bridge crack detection" (桥梁裂缝), 与 "steel surface defect" (钢材表面) 只共享方法 (YOLOv5) 但 object 不同。新 prompt 正确地 weak_reject 它。这是 Re1.2 prompt 比 Re1.1 更严格的体现。

### 24 候选批量测试 (开发期 snapshot, runner 部分输出)

| case | n_candidates | verify 路由 | fallback 触发 | verified | baseline |
| --- | --- | --- | --- | --- | --- |
| steel-yolov5 | 24 | repair (0 accept) | 3 batch × ~30% 触发 | 0 (严格 prompt 下全部 weak_reject) | - |
| medical-llm | 收集时被 timeout 终止 | - | - | - | - |

### 观察与分析

1. **Fallback 机制工作正常**: stepfun step-3.7-flash 在复杂 verify prompt 下返回 `{"":""}` thinking-only content → fallback 到 step-1v-32k 返回有效 JSON (per-candidate single object).

2. **Prompt 严格度**: Re1.2 新 per-candidate prompt 要求 `verdict "accept" requires relation_to_topic in (baseline, parallel) AND at least 1 hit_keywords`。比 Re1.1 prompt 更严格。

3. **Backfill 不足**: 当 `n_candidates=24` 全部被 weak_reject 时, 需要 multi-round repair 来搜索更多相关论文。Re1.2 runner 已实现 repair loop (最多 2 轮), 但单次 runner 运行时间 (topic_parser 30s + search_planner 22s + retrieve 48s + verify 443s + repair 33s ≈ 10 min) 可能 hit 10 min timeout。这是 runner 脚本的运行时间问题, 不是 graph 逻辑问题。

## Performance 数据 (单 topic aggregated)

| 指标 | 值 |
| --- | --- |
| topic_atoms LLM | 30s |
| search_planner LLM | 22s |
| paper_retriever (async 3-adapter) | 48s |
| paper_verifier (24 篇 x2 model calls, 3 batches) | 443s |
| targeted_repair LLM | 33s |
| **per-total (1 round)** | **~10 min** |

注: verify 时间可通过以下方式降低:
- 减少 batch 数 (BATCH=4 而非 BATCH=1)
- 给 stepfun 更多 max_tokens 减少 content 截断
- 后续引入 candidate 前 5 名的 precision search

## Fallback 调用统计 (本轮 runner fallback 总次数)

基于开发期 snapshot 估算, 每次 verify node call per-batch:
- 调用 stepfun step-3.7-flash → 成功率 ~70% (简单 prompt), 失败率 ~30%
- 失败 fallback 到 step-1v-32k

在 3 batch × 24 candidates 中, 估算 fallback 调用 ~20 次 (额外开销 ~28%)。

注意: 此数据来自 development 期的手工验证。全量统计需 runner 完整跑 3 topic (约 30-40 min wall clock time)。
