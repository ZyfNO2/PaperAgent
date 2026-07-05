# PaperAgent Re1.3 Loop 0 — 静态审计报告

> 日期: 2026-07-05
> 执行者: Codely CLI (执行 AI)

## 审计项目与结果

| # | 检查项 | 结果 | 说明 |
|---|---|---|---|
| 1 | `apps/web/index.html` 存在且为单文件 | ✅ PASS | HTML+CSS+JS 内联, 无外部依赖 |
| 2 | `quality_filter` 节点已注册 | ✅ PASS | REGISTRY 中存在 |
| 3 | `citation_expander` 节点已注册 | ✅ PASS | REGISTRY 中存在 |
| 4 | ResearchState 含新字段 | ✅ PASS | seed_papers, expanded_papers, filter_results, citation_expansion_done, surveys_found, repos_found |
| 5 | S2 适配器被 citation_expander 调用 | ✅ PASS | semantic_scholar_citations/references 被 import |
| 6 | 无硬编码黑名单 | ✅ PASS | rg 排除测试文件后 0 命中 |
| 7 | SSE 端点 `/stream` 存在 | ✅ PASS | StreamingResponse + text/event-stream |
| 8 | 无 `POST /seeds` 端点 | ✅ PASS | 无 @router.post 含 seed 的路由 |
| 9 | citation_expander 有 `_select_seeds` 函数 | ✅ PASS | 自动种子选取逻辑存在 |
| 10 | FastAPI 静态托管 apps/web | ✅ PASS | app.mount("/web", StaticFiles(...)) |
| 11 | `.env` 未被 tracked | ✅ PASS | .gitignore 中有 .env |
| 12 | 前端无外部依赖 | ✅ PASS | 无 `<script src="http">` 或 `<link href="http">` |
| 13 | 前端使用 EventSource | ✅ PASS | EventSource API 使用 |
| 14 | 前端有轮询 fallback | ✅ PASS | setTimeout/setInterval 存在 |
| 15 | 无 citation_tracker import | ✅ PASS | graph 目录下 0 命中 |
| 16 | quality_filter prompt 文件存在 | ✅ PASS | re13_quality_filter.py |
| 17 | citation_expander prompt 文件存在 | ✅ PASS | re13_citation_expander.py |

## 测试结果

```
19 passed, 0 failed (0.73s)
```

## 结论

Loop 0 静态审计全部通过, 所有 Re1.3 结构性要求已满足。
