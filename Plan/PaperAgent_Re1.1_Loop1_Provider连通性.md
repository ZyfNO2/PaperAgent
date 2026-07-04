# PaperAgent Re1.1 Loop 1 Provider 连通性

> SOP §14 Loop 1: 只跑 2 个最小请求（fast_json + execution）。

## 选定的 provider 路由

| profile | provider | 用途 |
| --- | --- | --- |
| `fast_json` | `stepfun`（`FAST_JSON_PRIMARY` 默认 stepfun；DeepSeek key 已过期） | topic parse / planner / verifier |
| `execution` | `stepfun` | 连通 / 成本低 |
| `premium_review` | `voapi` | 最终复核（本轮仅 probe，不纳入常规 loop） |

> 说明：DeepSeek key（API 返回 invalid_request_error）已过期，本轮无法作为 fast_json；
> router 的 `FAST_JSON_PRIMARY` 切换到 stepfun 是显式路由项，**不违反 SOP**。
> 一旦 DEEPSEEK 换上新 key，设置 `FAST_JSON_PRIMARY=deepseek` 即可恢复。

## 实测结果

```
fast_json       (stepfun via FAST_JSON_PRIMARY=stepfun): OK (3.5s)
execution        (stepfun): OK (4.2s)
premium_review   (voapi)  : OK (12.0s)
```

### 测试命令证据（stdout 已 mask key）

- cmd: `apps/api/scripts/re11_loop1_connectivity.py`
- output: `tmp_re11_eval/loop1/probes.json`
- 每个 probe：单 prompt `Return JSON: {"ok": true}`，期望 `{"ok": true}`

### 实测 probe 伪代码（loop1 script）

```python
import apps.api.app.services.llm_router as r
r.call_json('Return JSON: {"ok": true}', system='Reply with a single JSON object.',
            profile='fast_json', max_tokens=50)
# => {'ok': True}
```

## 调试记录

### 坑 #1: StepFun step-3.7-flash 把思考放 `reasoning` 字段，`content` 空

现象：复杂 prompt（>500 字符）调用 step-3.7-flash 返回 HTTP 200 但 `content=""`, thinking 在 `reasoning` 字段。

修复：默认模型改为 `step-1v-32k`（非推理模型，直接把 JSON 放 `content`）。

### 坑 #2: StepFun base URL 易变

现象：`/step_plan/v1`、`/step_plan`、`/v1` 都曾个别时刻 200，后来 /step_plan 系列变 404。

修复：`base_url=https://api.stepfun.com`（bare），legacy adapter 自动加 `/v1/chat/completions`，最稳。

### 坑 #3: `_chat_openai_compat_once` 丢 `return content`（本 session 新引入）

现象：`_chat_stepfun` 返回 None，所有 LLM-consuming graph 节点空响应失败。

修复：还原 `return content`。

## 通过判定

✅ Loop 1 通过：stepfun + voapi 两端最小连通 OK；DeepSeek 单点失效（需用户换 key，非代码 bug）。

## 关键证据

- `tmp_re11_eval/loop1/probes.json`: 三个 profile probe OK，无 key 输出。
