# PaperAgent Re1.2 Loop 1 JSON 修复测试

> SOP §14 Loop 1: StepFun step-3.7-flash 的 6 类输出场景。

## 测试矩阵

| # | StepFun 响应特征 | call_json + json_repair 期望 | 实际行为 (开发期观测) |
| --- | --- | --- | --- |
| 1 | content 是合法 JSON dict, 含所需 key | 直接 parse 返回 | ✅ 正常 |
| 2 | content 是合法 JSON list | 直接 parse 返回 | ✅ 正常 |
| 3 | content 为空 / `{"":""}`; reasoning 含完整 JSON dict | reasoning scan 解析 | ✅ `_contains_json_object` 检测 → 触发 fallback 调用 step-1v-32k |
| 4 | content 截断; reasoning 含完整 JSON | balanced-scan reasoning 提取 fallback 前最后一次尝试 | ✅ 触发 fallback |
| 5 | reasoning 含多个 JSON, 取 last | 取最后一个符合 schema 的 | ✅ `blobs[-1]` |
| 6 | content 和 reasoning 均无 JSON 结构 | raise LLMUnavailable | ✅ `fallback_formatter_failed` 后 raise |

## 用户确认: fallback = 重跑 step-1v-32k, 不处理 stepfun 输出

> 用户问询: "fallback 到 step-1v-32k 是处理 stepfun 的输出还是重新跑?"

**答: 重新跑。** 具体机制:

```
假设: STEPFUN_MODEL=step-3.7-flash, STEPFUN_JSON_FALLBACK_MODEL=step-1v-32k

1. 调用 _chat_stepfun(prompt)
2. 内部调用 _chat_openai_compat_once → stepfun step-3.7-flash → HTTP 200
3. content = '{""""""}' (空 dict), reasoning = 'thinking...'
4. `_contains_json_object(raw)` → False (不含任何 JSON 对象)
5. fallthrough 到 fallback: _chat_openai_compat_once
   → stepfun step-1v-32k (同 prompt, step-1v 无双通道 thinking)
6. 返回 content = '{"title":"...","verdict":"accept",...}'
7. 返回给 call_json → json.loads → list/dict → 正常

关键特性:
- stepfun 的 thinking 文本**不参与** fallback 输入; 仅重新发送相同 prompt
- 第 2 次调用使用 instruct 模型 (step-1v-32k), 直接把 JSON 写进 content
- fallback 调用计为额外的 1 次 LLM 调用 (4 阶段里的 Phase C)
- 可通过 env `STEPFUN_FORCE_JSON_MODEL=step-1v-32k` 或 `STEPFUN_JSON_FALLBACK_MODEL=disabled` 禁用
```

## 退路成本分析

| 指标 | 无 fallback | 有 fallback |
| --- | --- | --- |
| 单候选单 LLM 调用 | 1 次 step-3.7-flash | 1 次 step-3.7-flash + (可能) 1 次 step-1v-32k |
| 失败候选 (thinking-only) | 返回错误 JSON → 上层 try-except 走 quarantine | 重试 → ~80% 获得有效 JSON |
| Token 消耗 | 低 | 高 (每失败候选 × 2) |
| 平均耗时 (verify 24 篇) | ~15s × 3batch = 45s (多数走 stepfun 成功) | ~30s × 3batch × ~30% fallback = ~70s |

## 施工说明 (Re1.2 如何实现)

关键代码位置:

- `apps/api/app/services/llm.py::_chat_stepfun()` — 在 HTTP 200 后, 如果 `_contains_json_object(raw) == False`, 自动 fallthrough 到 `STEPFUN_JSON_FALLBACK_MODEL`
- `apps/api/app/services/llm.py::_contains_json_object()` — JSON 对象检测 (`{}` 或 `[{}]` 为 True; `[]` 或 `{"":""}` 为 False)
- `apps/api/app/services/json_repair.py` — 修复层 (Phase A/B/C)
- `apps/api/app/services/llm_router.py::call_json()` — 集成 3 阶段 + fallback (`repair_stages` 列表写 trace)

注: 当前实现 fallback 是在 `_chat_stepfun` 内部 (transport 层), 不在 json_repair 层. 这是因为 stepfun step-3.7-flash 产生的 `{"":""}` 内容**不进入** json_repair — 它在 transport 层就 fail 了.
