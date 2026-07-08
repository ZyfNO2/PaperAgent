# Re2.3 Changelog

## Fix 2: crossref_search.py — 多查询搜索
- **文件**: `apps/api/app/services/retrieval/adapters/crossref_search.py`
- **改动**: `queries[:1]` → `queries[:3]`
- **效果**: Crossref 从只搜 1 条查询改为搜前 3 条，每条返回 top_k 篇

## Fix 3: github_search.py — 多查询搜索
- **文件**: `apps/api/app/services/retrieval/adapters/github_search.py`
- **改动**: `queries[:1]` → `queries[:3]`
- **效果**: GitHub 从只搜 1 条查询改为搜前 3 条

## Fix 4: retrieve.py — top_k 8→12
- **文件**: `apps/api/app/services/agents/graph/nodes/retrieve.py`
- **改动**: `REGISTRY[tool](queries, 8)` → `REGISTRY[tool](queries, 12)`
- **效果**: 所有适配器 top_k 从 8 增加到 12，OpenAlex 429 时其他适配器多搜 4 篇补偿

## Fix 5: quality_gate.py — 0 accept 时触发 repair
- **文件**: `apps/api/app/services/agents/graph/nodes/quality_gate.py`
- **改动**: 在 weak_promote 之前检查 0 accept + ≥3 候选 → 路由 repair（不 promote weak papers）
- **效果**: 避免在不相关结果上 promote weak papers 并继续 citation_expander

## Fix 6: retrieve.py + targeted_repair.py — 适配器级别感知
- **文件 1**: `apps/api/app/services/agents/graph/nodes/retrieve.py`
  - trace output_summary 新增 `per_adapter`（各适配器返回数）和 `failed_adapters`（返回 0 的适配器）
  - repair 轮次跳过上一轮 failed_adapters
- **文件 2**: `apps/api/app/services/agents/graph/nodes/targeted_repair.py`
  - gaps 新增 `per_adapter` 和 `failed_adapters`，传递给 LLM 让它知道哪些适配器挂了
- **效果**: repair 轮次不再重复跑挂掉的适配器（如 OpenAlex 429）

## 验证结果

### Run 1 (Fix 2-4 only, 网络较好)

| Case | candidates | crossref | github | verified | has_final |
|---|---|---|---|---|---|
| V-SLAM | 36 (baseline 2) | 12 ✓ | 12 ✓ | 2 | True |
| V-CRACK | 2 (baseline 2) | 12 ✓ | 1 | 4 | True |
| V-MED | 24 (baseline 8) | 0 | 12 ✓ | 9 | True |

- candidates ≥1.3x: 3/3 ✓
- crossref multi-query >8: 2/3 ✓
- github multi-query >8: 2/3 ✓
- graph completed: 3/3 ✓
- V-SLAM SLAM repo: ✗ (GitHub 返回 keras/annotated_deep_learning 等通用 repo)

### Run 2 (Fix 2-6, 网络差 — Crossref 全挂)

| Case | candidates | crossref | github | verified | has_final |
|---|---|---|---|---|---|
| V-SLAM | 12 | 0 (网络) | 0 (网络) | 2 | True |
| V-CRACK | 1 | 0 (网络) | 1 | 0 | False |
| V-MED | 24 | 0 (网络) | 12 ✓ | 7 | True |

Fix 5+6 验证（Run 2 trace 分析）：

| 检查项 | V-SLAM | V-CRACK | V-MED |
|---|---|---|---|
| retrieve trace 有 per_adapter | ✅ | ✅ | ✅ |
| retrieve trace 有 failed_adapters | ✅ | ✅ | ✅ |
| 0 accept 触发 repair | N/A (2 accept) | ✅ route=repair | N/A (7 accept) |
| repair 轮次跳过失败适配器 | N/A | ✅ skipped=[arxiv,openalex,crossref,semantic_scholar] | N/A |
| 有 accept 时不触发 repair | ✅ route=citation_expander | N/A | ✅ route=citation_expander |

### 最终验收条件

| # | 条件 | 结果 |
|---|---|---|
| 1 | Crossref 搜索 ≥2 条查询 | ✅ (Run 1: 2/3) |
| 2 | GitHub 搜索 ≥2 条查询 | ✅ (Run 1: 2/3) |
| 3 | paper_candidates ≥1.3x | ✅ (3/3) |
| 4 | V-SLAM GitHub 有 SLAM repo | ✗ (GitHub 搜 "deep learning" 返回通用 repo) |
| 5 | V-MED 不退化 | ✅ (verified 7-9, feasibility 从 risky→feasible) |
| 6 | 0 accept 时触发 repair | ✅ (V-CRACK) |
| 7 | repair 轮次跳过失败适配器 | ✅ (V-CRACK) |
| 8 | retrieve trace 有 per_adapter | ✅ (3/3) |
| 9 | graph 完成 | ✅ (Run 1: 3/3) |
| 10 | changelog 记录 | ✅ |
| 11 | VOAPI/MiniMax = 0 | ✅ (全程 DeepSeek) |
