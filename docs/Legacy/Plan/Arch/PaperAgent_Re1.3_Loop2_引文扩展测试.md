# PaperAgent Re1.3 Loop 2 — 引文扩展测试报告

> 日期: 2026-07-05
> 执行者: Codely CLI (执行 AI)

## 测试内容

构造 3 篇种子论文, 验证 citation_expander 的种子选取、去重、并发扩展、S2 API 失败处理。

## 测试用例

### 种子选取

| # | 测试 | 结果 |
|---|---|---|
| 1 | `test_select_seeds_picks_most_relevant` — 按 relevance_score 排序 | ✅ PASS |
| 2 | `test_select_seeds_skips_no_id` — 无标识符的论文被跳过 | ✅ PASS |
| 3 | `test_select_seeds_top_n_limit` — top_n 限制生效 | ✅ PASS |
| 4 | `test_select_seeds_has_selection_reason` — 有 seed_selection_reason 字段 | ✅ PASS |

### 去重

| # | 测试 | 结果 |
|---|---|---|
| 5 | `test_dedup_removes_duplicates` — paperId 去重 | ✅ PASS |
| 6 | `test_dedup_removes_existing_titles` — 与已有论文去重 | ✅ PASS |
| 7 | `test_normalize_title` — 标题规范化 | ✅ PASS |

### 综述/Repo 识别

| # | 测试 | 结果 |
|---|---|---|
| 8 | `test_identify_surveys` — 识别 survey/review 论文 | ✅ PASS |
| 9 | `test_extract_repos` — 从论文元数据提取 GitHub URL | ✅ PASS |

### 节点集成

| # | 测试 | 结果 |
|---|---|---|
| 10 | `test_citation_expander_node_with_mocked_s2` — 全节点 mock S2 测试 | ✅ PASS |
| 11 | `test_citation_expander_no_seeds` — 无种子时优雅跳过 | ✅ PASS |
| 12 | `test_citation_expander_s2_failure_graceful` — S2 失败不阻塞管道 | ✅ PASS |
| 13 | `test_citation_expander_trace_recorded` — trace 记录 per-seed 信息 | ✅ PASS |

## 测试结果

```
13 passed, 0 failed
```

## 关键发现

1. 种子选取算法正确: 按 hit_keywords ∩ topic_atoms 重合度排序, baseline/parallel 加权, 无标识符跳过
2. 去重策略: 优先 paperId, fallback DOI, 再 fallback 标题 normalized
3. S2 API 失败时返回空列表, 不阻塞管道
4. 并发执行: `asyncio.gather` + `Semaphore(3)` 限制并发
5. 扩展论文有 `expanded_from_seed` 字段, 来源可追溯

## 结论

Loop 2 引文扩展测试全部通过。
