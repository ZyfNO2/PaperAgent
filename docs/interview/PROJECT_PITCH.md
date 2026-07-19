# PaperAgent 项目讲解稿

## 30 秒版本

PaperAgent 是一个有边界的科研 Agent 后端。我主要解决的不是“让模型自动写论文”，而是把研究任务做成可持久化、可取消、可审查、可预算控制的异步工作流。系统使用 FastAPI、SQLite、LangGraph 和结构化 LLM 输出，支持任务幂等、SSE 事件流、文献检索、人工 Review、确定性导出以及显式授权的插件机制。

## 2 分钟版本

项目入口是 FastAPI 异步任务接口。客户端提交任务时必须携带 Idempotency-Key，后端将规范化请求做哈希，在 SQLite 的立即事务里完成幂等检查、任务创建和首个事件写入。同一个键和同一个请求会复用原任务；同一个键对应不同请求会返回 409。

执行层是单进程的持久化 Runner。它从 SQLite 原子领取排队任务，再交给 TaskExecutor。Demo Executor 用于无凭证验收；Real Executor 运行有界 LangGraph，接入文献 Provider 和结构化 LLM Provider。每次模型调用都受到调用次数、Token、时间和可选费用预算约束。结构化输出失败时只允许一次 Repair，并与网络重试分开计费和记录。

任务进度写入持久化事件表，前端既可以分页读取，也可以通过 SSE 按序号恢复。用户可以取消任务；运行中取消采用协作式边界检查。进程重启后，系统不会自动重放可能已经计费的远程调用，而是将遗留运行任务标记为 PROCESS_RESTARTED，这属于有意的 Fail-Closed 设计。

完成后，证据会进入人工 Review。Review 使用乐观版本防止并发覆盖，最终导出带 SHA-256 和条目数。插件系统默认只加载内置插件，外部 Entry Point 必须在当前命令中精确授权，而且明确声明授权不等于沙箱。

## 5 分钟展开顺序

1. **业务问题**：科研 Agent 的风险不是只会答错，还包括重复计费、错误引用、不可恢复状态和不可解释失败。
2. **接口合同**：202 异步任务、幂等键、任务状态、事件游标、取消、Review、Export。
3. **一致性设计**：SQLite WAL、立即事务、原子 Claim、单调事件序号、乐观 Review Version。
4. **Agent 执行**：有界 LangGraph、Provider 抽象、结构化 Schema、一次 Repair、预算跨 Retry/Repair 共享。
5. **失败设计**：429/5xx 有界重试；401/403、预算、Schema 能力错误 Fail Closed；重启不自动重放。
6. **安全边界**：Key 只来自进程配置；Telemetry 脱敏；外部插件显式授权；无公开多租户声明。
7. **质量证据**：双 Python CI、严格 Mypy、90% 覆盖率门禁、浏览器垂直链路、Docker、真实文献 Provider Smoke。
8. **当前限制**：单进程、SQLite、无插件沙箱、真实 Mistral 与科学质量评测仍属于外部 Release Evidence。

## 可量化成果

- Python 3.11 / 3.12 双版本验证；
- Ruff、严格 Mypy、分支覆盖率门禁；
- 任务幂等、并发 Claim、取消、重启恢复测试；
- 48 条开发评测集，区分 in-domain、OOD、证据不足和对抗场景；
- 浏览器 Submit → Progress → Review → Export 垂直 Smoke；
- OpenAlex、arXiv、Crossref、DataCite 真实连接验证；
- 插件 JSON 合同、Entry Point 授权与竞态安全输出。

## 不应该夸大的内容

- 不说已经达到生产级多租户；
- 不说 SQLite 支持无限并发；
- 不说 Mock 或 Demo 证明真实模型质量；
- 不说 Schema 合法等于科研结论正确；
- 不说外部插件已经沙箱化；
- 不说 v0.6 已完成真实 Mistral 和盲审 Release Gate。
