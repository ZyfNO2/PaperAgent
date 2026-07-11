# PaperAgent Re7.1：长任务运行控制 MVP SOP

> 目标：让外部用户能可靠地提交、查看、取消、恢复研究任务，并能看到缓存命中与成本预算；不在本期做分布式多租户调度。

## 目录

1. MVP 边界
2. 架构与状态机
3. 接口
4. 缓存与成本
5. 实施顺序
6. 验收与回滚

## 1. MVP 边界

采用 **SQLite + 单 worker + 持久化事件日志**，适合作品集和 5--20 人 Beta。任务真相不再只有
浏览器 SSE 或 `tmp_re13_eval` 目录：SQLite 记录状态，case 目录保留 artifact/checkpoint/trace。
后续扩展到 Postgres + Redis/RQ/Celery 时保持 API 和状态机不变。

不做：支付、跨地域 worker、exact token billing、自动重跑失败任务。

## 2. 架构与状态机

```text
POST job -> queued -> leased -> running -> succeeded
                       |          |-> cancel_requested -> cancelled
                       |          |-> budget_exhausted -> partial
                       |          `-> failed (typed error)
                       `-> worker lost -> resumable
POST resume ------------------------------> queued
```

最小表：

| 表 | 关键字段 |
|---|---|
| `research_jobs` | job_id, case_id, user_id, state, lease_until, checkpoint_ref, idempotency_key, submitted/updated_at |
| `job_events` | event_id, job_id, sequence, type, payload_redacted, created_at |
| `job_budget` | job_id, max_llm_calls, max_input/output_tokens_est, max_wall_s, used_* |
| `cache_entries` | key, scope, value_ref, expires_at, producer_version |

取消必须是 cooperative：每个 graph node、重试等待、外部请求和 LLM 调用前检查
`cancel_requested`；不得杀进程或留下半写 JSON。恢复仅从已完成 node 的 checkpoint 继续，
并固化 provider/model/prompt/contract snapshot。

## 3. API

- `POST /api/v1/jobs`：topic、constraints、budget、idempotency key；返回 job_id；
- `GET /api/v1/jobs/{id}`：状态、当前 node、预算、partial artifact；
- `GET /api/v1/jobs/{id}/events?after=`：可重连事件流；
- `POST /api/v1/jobs/{id}/cancel`：幂等地标记取消；
- `POST /api/v1/jobs/{id}/resume`：仅 `failed|cancelled|partial|resumable` 可用；
- `GET /api/v1/jobs/{id}/artifacts`：只列脱敏、已完成 artifact。

状态转换由服务端单点校验；SSE 只是投影。所有 API 返回 `run_snapshot_id`，保证重跑可解释。

## 4. 缓存与成本

缓存键必须含 `raw_topic hash + normalized plan + source policy + provider/model + prompt/contract version`。
可缓存：公开检索 metadata、adapter 响应、确定性解析、RAG index；不可跨用户缓存：用户 PDF、API key、
带私人上下文的 LLM 输出。缓存命中须写 event，允许用户看到“结果来自缓存”。

成本先采用估算而非虚假精确：每次调用记录模型、输入/输出字符或 provider usage、retry/fallback、
预计成本区间。预算触发时停止后续 LLM 节点并返回 `partial`，保留已有证据。

## 5. 实施顺序

1. 建 schema/repository 和状态转换单测；
2. 把现有提交入口包成 `Job`，保留原 research API 兼容；
3. worker lease、checkpoint、cancel probe；
4. 事件重连、前端取消/恢复/预算面板；
5. 缓存与 budget guard；
6. worker crash、重复提交、超预算、取消 race 回归。

## 6. 验收与回滚

- [ ] 进程重启后，运行任务成为 `resumable` 而非消失；
- [ ] cancel 在一个 node 边界内生效，且不产生后续 LLM 调用；
- [ ] 同 idempotency key 不生成双任务；
- [ ] 预算耗尽返回已有 artifact + 明确原因，不伪造完成；
- [ ] SSE 断线重连不丢失 event sequence；
- [ ] 缓存命中不改变 evidence/provenance，私人资料不跨用户复用；
- [ ] 失败/取消/恢复各有 trace，raw key 不进入 DB/event。

回滚：feature flag `JOB_RUNTIME_ENABLED=false` 回到现有单进程调用；旧 case 目录只读可查。
