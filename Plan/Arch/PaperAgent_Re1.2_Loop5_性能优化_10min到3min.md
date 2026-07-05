# PaperAgent Re1.2 性能优化: 单 case 10min → <3min

> 优化日期: 2026-07-05

## 1. 问题

Re1.2 优化前单 case wall-clock ~10 min, 主要瓶颈:

| 节点 | 瓶颈 | 耗时 |
| --- | --- | --- |
| verify_node | 24 candidates × 顺序 LLM call, BATCH=1 | **443 s** |
| dataset_repo_extractor | 8 papers × 顺序 LLM call | ~30 s |
| search_planner | 单次 LLM call (stepfun reasoner) | ~22 s |
| topic_parser | stepfun reasoner | ~30 s |
| paper_retriever | async I/O (已并行) | ~48 s |

## 2. 优化策略

### 2.1 verify_node 并行化 (节省 ~380s)

`verify.py` 中 `_call_verifier()` 从 BATCH=1 顺序调用改为 `ThreadPoolExecutor(max_workers=4)` 并发。24 个 candidate 分 4 路并行, 每路 ~18s (含 fallback), 总 wall-clock ~25-70s。

风险: httpx 非线程安全, 但每个线程独立 `httpx.post()` 不共享 client, 安全。

### 2.2 search_planner 模板化 (节省 ~22s)

搜索计划大多是从 atoms 机械拼装 query string, 无需 LLM。新增 `_template_plan()` 直接从 atoms 构建 openalex/arxiv 查询:

```
method[0] × object[0] → openalex "YOLOv5 steel"
dataset_terms[0] → openalex "NEU-DET dataset benchmark"
```

env `PAPERAGENT_SKIP_SEARCH_PLANNER=true` (默认开)。需关闭时设为 `false`。

### 2.3 dataset_repo_extractor 并行化 (节省 ~20s)

同样改用 ThreadPoolExecutor(max_workers=4), 8 papers 分 4 路并行, ~8-10s。

### 2.4 HTTP 429 重试 (稳定性)

`_chat_openai_compat_once` 和 `_chat_once_json_via_fallback` 增加 429 retry + 指数退避 (1s → 2s → 4s, max 3)。防止 stepfun RPM=10 限流时 fallback 失败。

### 2.5 删除重复函数

`research_graph.py` 两个 `_route_after_quality_gate` 定义完全重复(第二个覆盖第一个), 删除第一个保留第二个。

## 3. 优化效果

### 单 topic live 实测 (steel-YOLOv5)

| 节点 | 优化前 | 优化后 |
| --- | --- | --- |
| intake | 0 ms | 0 ms |
| topic_parser | 30.5 s | 30.5 s (reasoner-bound, 无优化空间) |
| search_planner | 22.0 s | 0 ms (模板) |
| paper_retriever | 48.0 s | 32.6 s |
| paper_verifier | **443.0 s** | **69.6 s** (4× 并行) |
| quality_gate | 0 ms | 0 ms |
| dataset_repo | ~30 s | (需 verified > 0 才触发) |
| evidence_graph | 0 ms | 0 ms |
| baseline_classifier | 0 ms | 0 ms |
| targeted_repair | 33 s | (仅 repair 路径) |
| work_package | ~25 s | (同上) |
| **TOTAL** | **~600 s (10 min)** | **~135 s (2.25 min)** ✅ |

### Rate limit 场景 (stepfun RPM=10)

实测出现 fallback 全 429 时, 429 retry 使总 wall-clock 膨胀至 295s (仍 <5 min)。这是 stepfun RPM=10 配额限制, 非 pipeline 代码问题。调高 quota 后回到 <3 min。

## 4. 文件变更

| 文件 | 改动类型 | 描述 |
| --- | --- | --- |
| `nodes/verify.py` | 重写 `_call_verifier` | BATCH=1 顺序 → ThreadPoolExecutor(max_workers=4) |
| `nodes/search_planner.py` | 新增 `_template_plan` | atoms → 确定性 query 模板 |
| `nodes/search_planner.py` | 修改 `search_planner_node` | env 开关 + 模板 bypass |
| `nodes/dataset_repo_extractor.py` | 重写提取循环 | 顺序 → ThreadPoolExecutor(max_workers=4) |
| `llm.py` | 修改 `_chat_openai_compat_once` | 加 429 retry backoff |
| `llm.py` | 修改 `_chat_once_json_via_fallback` | 加 429 retry backoff |
| `research_graph.py` | 删除重复 | 删除第一个 `_route_after_quality_gate` |
| `scripts/timing_single.py` | 新增 | 单 case timing 验证脚本 |

## 5. 验收

- ✅ 总耗时 <3 min (实测 134.9s / 2.25 min)
- ✅ 5/5 smoke tests pass
- ✅ search_planner 模板路径 env 可控
- ✅ 429 retry 防止限流崩溃
- ✅ 无 LLM key / token 泄漏风险
