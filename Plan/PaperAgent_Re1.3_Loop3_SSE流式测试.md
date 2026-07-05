# PaperAgent Re1.3 Loop 3 — SSE 流式测试报告

> 日期: 2026-07-05
> 执行者: Codely CLI (执行 AI)

## 测试内容

验证 SSE 流式端点 `/api/v1/research/{case_id}/stream` 的结构、事件类型、响应格式。

## 测试用例

| # | 测试 | 结果 | 说明 |
|---|---|---|---|
| 1 | `test_sse_endpoint_exists` | ✅ PASS | /stream 路由已注册 |
| 2 | `test_expanded_endpoint_exists` | ✅ PASS | /expanded 路由已注册 |
| 3 | `test_expanded_endpoint_404` | ✅ PASS | 不存在的 case 返回 404 |
| 4 | `test_sse_event_format` | ✅ PASS | _sse_event 格式正确 (event: + data: + \n\n) |
| 5 | `test_sse_event_types_defined` | ✅ PASS | 所有预期事件类型在源码中定义 |
| 6 | `test_streaming_response_used` | ✅ PASS | StreamingResponse + text/event-stream |

## SSE 事件类型

以下事件类型已在 SSE 端点中实现:

| 事件类型 | 时机 | data 内容 |
|---|---|---|
| `search_started` | 连接建立时 | {case_id, status} |
| `filter_result` | quality_filter 完成 | {kept, dropped} |
| `verify_completed` | verify 完成 | {accepted, rejected, round} |
| `expansion_started` | citation_expander 选种后 | {n_seeds, seed_titles} |
| `expansion_completed` | citation_expander 完成 | {total_expanded, n_surveys, n_repos} |
| `node_complete` | 后续节点完成 | {node, output, elapsed_s} |
| `done` | 最终完成 | {case_id, total_elapsed_s} |
| `error` | 错误 | {node, message} |

## 测试结果

```
6 passed, 0 failed
```

## 已知限制

- SSE 流式测试使用 TestClient 无法完整测试异步流 (async generator 在 TestClient 中可能挂起), 因此 Loop 3 仅测试结构正确性
- 实际流式功能在 Loop 4 (前端 Smoke) 和 Loop 5 (真实样例) 中验证

## 结论

Loop 3 SSE 流式测试全部通过。端点结构、事件类型、响应格式均符合 SOP 要求。
