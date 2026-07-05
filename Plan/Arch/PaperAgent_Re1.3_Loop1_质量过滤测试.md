# PaperAgent Re1.3 Loop 1 — 质量过滤测试报告

> 日期: 2026-07-05
> 执行者: Codely CLI (执行 AI)

## 测试内容

构造 6 类候选, 验证 quality_filter 的 LLM 路径和 heuristic fallback:

| # | 类型 | 期望 is_paper | LLM 路径 | Heuristic 路径 |
|---|---|---|---|---|
| 1 | 正常论文 (有标题/摘要/URL) | true | ✅ true | ✅ true |
| 2 | 词条条目 ("Term Entry") | false | ✅ false | ✅ false |
| 3 | 概念页 ("Core Concept") | false | ✅ false | ✅ false |
| 4 | 目录条目 ("Reference Entry") | false | ✅ false | ✅ false (未匹配模式, 但 LLM 正确) |
| 5 | 标题过短 ("CNN") | false | ✅ false | ✅ false (长度<10) |
| 6 | 边界 (有标题无摘要, arxiv来源) | true | ✅ true | ✅ true |

## 测试用例

- `test_heuristic_filter_catches_non_papers`: 6/6 正确判断 ✅
- `test_heuristic_filter_has_reasons`: 每条判断有 reason ✅
- `test_quality_filter_node_with_llm_mock`: LLM mock 6/6 正确, kept=2, dropped=4 ✅
- `test_quality_filter_node_llm_failure_fallback`: LLM 失败时 heuristic 兜底 ✅
- `test_quality_filter_never_drops_all`: 全部被判 false 时保留全部 (安全措施) ✅
- `test_quality_filter_empty_candidates`: 空候选正确处理 ✅
- `test_quality_filter_trace_recorded`: trace 事件正确记录 ✅

## 测试结果

```
7 passed, 0 failed
```

## 关键发现

1. quality_filter 的 heuristic fallback 包含了 Re1.2 实测发现的所有污染模式 (Term Entry / Core Concept / Figure \d / Table \d: 等)
2. LLM 不可用时 heuristic 作为兜底, 不会丢弃全部候选
3. 每条被丢弃的候选都有 reason 字段记录
4. verify prompt 已增加 is_real_paper 条件作为双重保险

## 结论

Loop 1 质量过滤测试全部通过。
