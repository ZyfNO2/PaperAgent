# PaperAgent 后端面试问答

## 为什么接口返回 202，而不是等待 Agent 执行完成？

Agent 执行包含检索和远程模型调用，延迟不稳定。接口先事务性持久化任务并返回 202，客户端通过任务查询或 SSE 获取进度。这样可以支持超时隔离、取消、断线恢复和重试策略，也避免占用一个长 HTTP 请求。

## Idempotency-Key 是怎么实现的？

后端对校验后的请求做规范化 JSON 序列化和 SHA-256。SQLite 表中 Idempotency-Key 唯一。创建任务时使用 `BEGIN IMMEDIATE`：

- 键不存在：插入任务和 `task.queued` 事件；
- 键存在且 Hash 一致：返回原任务；
- 键存在但 Hash 不同：返回 409。

这防止客户端超时重试产生重复任务和重复模型费用。

## 为什么选择 SQLite？

当前边界是本地单用户和单进程 Worker。SQLite 无外部依赖，事务语义清楚，适合复现测试。WAL 和 Busy Timeout 足以支撑 MVP。它不是永久架构；当需要多实例、多租户、水平 Worker 或更高写并发时，应迁移 PostgreSQL 和分布式队列。

## 如何保证任务不会被重复领取？

领取逻辑在立即事务中完成。先按创建时间查询最旧的 queued 任务，再用带状态条件的 UPDATE 将它改为 running。如果影响行数不是 1，则放弃领取。状态变化和 `task.started` 事件处在同一事务里。

## SSE 断线后怎么恢复？

事件持久化在 SQLite，每个任务有单调递增 Sequence。SSE 的 `id` 就是 Sequence。客户端保存最后游标，重连后从该序号继续读取，不依赖进程内 Pub/Sub 状态。

## 取消是强制中断吗？

不是。运行中取消先持久化为 `cancel_requested`，Executor 在节点或调用边界检查 Cancellation Probe。这样不会在线程任意位置破坏状态。已发出的远程调用可能仍完成并计费，这是残余风险。

## 进程重启后为什么不自动重试运行中的任务？

远程调用可能已经成功，但本地来不及持久化结果。如果自动重放，可能重复计费或重复副作用。在没有 Provider 级 Durable Idempotency 前，系统将遗留任务标记为 `PROCESS_RESTARTED`，由用户决定是否用新幂等键重提。

## 如何管理数据库升级？

启动时检查 `PRAGMA user_version`，维护 `schema_migrations` 记录。低版本执行幂等迁移；高于当前程序支持版本的数据库直接拒绝启动，避免旧程序破坏新数据。

## 为什么没有直接使用 Celery？

Celery 会引入 Broker、Worker、序列化、重试和部署复杂度，而当前目标是验证任务合同和 Agent 失败语义。项目通过 `TaskExecutor` 和 Repository 协议保留迁移路径。需要多 Worker、延迟任务和分布式 Lease 时再引入队列更合理。

## 如何做可观测性？

分三层：

1. Durable Task Events：解释单任务发生了什么；
2. `/readyz`：判断数据库、Executor 和 Schema 是否可用；
3. `/v1/diagnostics/runtime` 与 `/metrics`：提供低基数、无敏感内容的状态和 Prometheus 文本指标。

调用级 Telemetry 只记录 ID、模型、延迟、Token、费用估算和错误分类，不保存凭证或 Chain-of-Thought。

## Review 并发怎么处理？

Review 请求携带 `expected_version`。数据库只在当前版本一致时更新并递增版本，旧页面提交会得到 409，而不是覆盖其他人的更新。这是轻量级乐观锁。

## 怎样判断需要从 SQLite 升级？

不是按“项目看起来大不大”，而是看具体触发条件：

- 多 API 实例；
- 独立 Worker 扩容；
- 任务吞吐或写锁等待超过目标；
- 多租户隔离；
- 需要分布式事务、Lease 或复杂查询；
- 备份、复制和高可用成为硬要求。
