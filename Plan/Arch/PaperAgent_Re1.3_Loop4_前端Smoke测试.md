# PaperAgent Re1.3 Loop 4 — 前端 Smoke 测试报告

> 日期: 2026-07-05
> 执行者: Codely CLI (执行 AI)

## 测试内容

使用 `frontend_validator.py` 自测验证器检查 `apps/web/index.html` 的基本正确性。

## 验证结果

```json
{
  "checks": [
    "no_external_dependencies",
    "uses_eventsource",
    "has_topic_input",
    "sse_event_listeners",
    "has_polling_fallback"
  ],
  "passed": 5,
  "failed": []
}
```

## 检查项详情

| # | 检查项 | 结果 | 说明 |
|---|---|---|---|
| 1 | 无外部依赖 | ✅ PASS | 无 `<script src="http">` 或 `<link href="http">` |
| 2 | 使用 EventSource | ✅ PASS | `new EventSource(...)` 用于 SSE 消费 |
| 3 | 有题目输入框 | ✅ PASS | `<input type="text" id="topic">` 存在 |
| 4 | SSE 事件监听完整 | ✅ PASS | 监听 adapter_result, verify_result, node_complete, done, filter_result, expansion_started, expansion_completed, search_started, error |
| 5 | 有轮询 fallback | ✅ PASS | `setTimeout` + `setInterval` 用于 SSE 不可用时的轮询 |

## 前端功能

1. **题目输入**: 用户输入研究题目, 点击"开始研究"
2. **SSE 连接**: POST 提交后通过 EventSource 连接 `/api/v1/research/{case_id}/stream`
3. **实时渲染**:
   - 搜索阶段: 适配器结果逐条显示
   - 质量过滤: 显示保留/丢弃数量
   - 论文列表: verify 标记 (✓/✗/⚠) 实时更新
   - 引文扩展: 种子列表 + 扩展数量
   - 分析阶段: 节点完成增量渲染
   - 最终结果: 完整报告
4. **轮询 fallback**: SSE 不可用时通过 `setTimeout` + `setInterval` 轮询 `/status`

## 技术约束满足

- ✅ 不依赖任何框架/构建工具 — 原生 HTML + CSS + JS
- ✅ CSS 内联在 `<style>` 标签中
- ✅ JS 内联在 `<script>` 标签中
- ✅ 使用 EventSource API 消费 SSE
- ✅ SSE 不可用时 fallback 到轮询

## 结论

Loop 4 前端 Smoke 测试全部通过。前端满足 SOP §5.6 的所有技术约束。

> **注意**: 前端实际交互测试 (输入题目 → 实时显示) 需要启动 FastAPI 服务器并手动验证, 属于 Loop 5 真实样例测试的一部分。
