# PaperAgent v0.1 完成后的版本路线图

> Status: `PROPOSED ROADMAP`  
> Scope: `v0.2 → v1.0`  
> Precondition: v0.1 已通过 `docs/v0.1/ACCEPTANCE.md` 的全部 P0 验收项并合并到 `master`。

## 1. 总体原则

v0.1 之后不继续无边界加节点。每个版本只解决一个主问题，并继续执行强制 TDD：

```text
冻结需求与测试合同
→ 新建版本分支
→ RED
→ GREEN
→ REFACTOR
→ OOD / E2E 验收
→ 合并 master
→ 打版本标签
```

长期目标是形成一个可半自主运行、可暂停、可恢复、可审计的研究规划 Agent，而不是一次性自动写论文的黑箱系统。

## 2. v0.1 完成后的立即工作

在开始 v0.2 前，先完成一个短暂的稳定阶段：

1. 合并 `v0.1` 到 `master`；
2. 创建标签 `v0.1.0`；
3. 记录真实测试结果、已知限制和未完成项；
4. 冻结 v0.1 的 State、Node、Fixture 和 Trace schema；
5. 为破坏性变更建立 migration note；
6. 删除仅用于开发的临时 fixture 和未使用 stub；
7. 从 `master` 创建 `v0.2` 分支。

进入 v0.2 的前提：Fake Provider 下全部图路径稳定、循环有界、Trace 完整、OOD 无旧案例泄漏。

---

## 3. v0.2 — 真实 Provider 与可信检索

### 核心目标

把 v0.1 的确定性骨架接入真实 LLM 和真实检索，但不扩大图结构。

### 实现范围

- `LLMProvider` 正式接口；
- 至少一个真实结构化输出模型适配器；
- `SearchProvider` 正式接口；
- 论文、网页、仓库三类基础来源；
- Provider timeout、bounded retry、rate limit 和 usage metadata；
- Evidence URL、DOI、仓库地址的基础验证；
- Prompt registry 和 prompt version；
- 真实 Provider smoke test，默认不进入普通离线 CI。

### TDD 重点

- Provider SDK 异常必须归一化；
- malformed JSON 不得进入 State；
- 搜索失败不得伪造结果；
- rejected/pending Evidence 不得支持最终结论；
- 同一个 fixture 在不同 Prompt 文本下仍返回相同测试结果。

### 暂不实现

- 多 Provider 自动路由；
- 向量数据库；
- 长期记忆；
- Multi-Agent；
- 完整 PDF 深度解析。

### 验收

- 真实 Provider happy path 可完成；
- 离线测试不依赖网络；
- 正常路径核心 LLM 调用仍不超过 5 次；
- Provider 错误均有稳定错误类型和 Trace；
- 无来源时明确 BLOCKED，不补造文献。

---

## 4. v0.3 — Checkpoint、持久化、Trace 与 Replay

### 核心目标

让一次 Agent 运行可以安全暂停、恢复和审计。

### 实现范围

- SQLite Checkpointer；
- run/thread/session 基础合同；
- Node 级 checkpoint；
- Human interrupt/resume；
- versioned `TraceEvent`；
- payload redaction；
- JSONL 或 SQLite Trace store；
- read-only trace inspector；
- recorded replay；
- checkpoint schema migration 最小机制。

### 借鉴来源

可以借鉴 PaperClaw 已验证的 Context、Session、Trace、Safe Resume 和 Recorded Replay 合同，但不得整体复制无关子系统。

### TDD 重点

- interrupt 后状态可恢复；
- 已完成副作用不被重复执行；
- replay 不调用真实模型和工具；
- Trace 中可区分真实调用、retry、fallback 和 replay；
- Secret 不进入持久化 payload。

### 验收

- 任意顶层节点后可恢复；
- Human review 路径可跨进程恢复；
- recorded replay 与原始节点序列一致；
- Trace 完整率 100%；
- checkpoint 损坏时显式失败，不静默重置。

---

## 5. v0.4 — 自动评估与质量基线

### 核心目标

建立可重复的 Agent 质量评估，不依赖主观展示。

### 实现范围

- deterministic graph eval；
- schema success rate；
- task completion rate；
- Evidence binding coverage；
- unsupported claim detection；
- retry/repair/tool failure 指标；
- Token、成本、P50/P95 延迟；
- OOD 测试集扩展；
- legacy entity leakage scanner；
- golden trace 和 regression report；
- 可选的 LLM reviewer 实验，但不得覆盖硬规则。

### 测试集结构

至少覆盖：

- CV；
- NLP；
- 推荐系统；
- 时间序列；
- 数据库；
- 软件工程；
- 跨学科问题；
- 信息不足问题；
- 不可完成问题；
- 恶意或诱导伪造引用的问题。

### 验收

- 每次版本提交都可生成确定性评估报告；
- 所有 claim 可追溯到 Evidence 或标记为 proposed/inferred；
- OOD 任务无固定案例污染；
- 真实 Provider 指标与 Fake Provider 指标分开报告；
- Mock 结果不得被称为真实 E2E。

---

## 6. v0.5 — API、任务控制与 Human-in-the-Loop

### 核心目标

把核心 Agent 封装成可供前端或其他服务调用的半自主任务服务。

### 实现范围

- FastAPI 最小接口；
- 创建 run、读取状态、读取报告；
- pause、resume、cancel；
- Human review 提交接口；
- 幂等 request key；
- 任务状态机；
- 基础认证和速率限制；
- API contract tests；
- 不包含完整 Web UI。

### 状态建议

```text
created
→ running
→ waiting_for_human
→ running
→ completed | blocked | failed | cancelled
```

### 验收

- API 重复提交不会重复创建副作用；
- cancel 后不再调用模型或检索；
- waiting_for_human 可恢复；
- 所有 API 状态与 LangGraph State 一致；
- 错误响应不泄漏 Prompt、Secret 或内部堆栈。

---

## 7. v0.6 — 研究材料工作区

### 核心目标

让用户材料成为一等 Evidence，而不是附加文本。

### 实现范围

- 用户上传材料登记；
- PDF、Markdown、纯文本基础解析；
- source provenance；
- 文档 chunk 和稳定 ID；
- 用户材料与网络材料统一 Evidence contract；
- 冲突来源标记；
- accepted/rejected 人工操作；
- 报告导出为 Markdown/JSON；
- 暂不运行用户代码。

### TDD 重点

- 同一文档重复上传去重；
- chunk ID 稳定；
- 材料删除后引用失效可检测；
- 用户材料优先级不等于真实性；
- PDF 解析失败不得伪造正文。

### 验收

- 用户材料可完整进入检索、综合、方法设计和最终报告；
- 每个引用可回到原文件和位置；
- 冲突来源不会被静默合并；
- 解析失败有明确状态。

---

## 8. v0.7 — ContextBuilder 与上下文预算

### 核心目标

解决长任务中的上下文膨胀、Prompt 偏移和无关 State 注入。

### 实现范围

```text
collect
→ validate
→ scope
→ deduplicate
→ conflict check
→ estimate tokens
→ select
→ compact
→ render
```

- Node 最小上下文投影；
- required constraints 永久保留；
- Evidence reference 永久保留；
- 分层摘要；
- Token budget；
- 冲突检测；
- context manifest；
- Prompt injection 基础防护。

### 暂不实现

- 长期个人记忆；
- 自动向量记忆写入；
- 跨用户共享记忆。

### 验收

- Workflow 不再直接读取完整 State；
- 压缩前后 required constraints 一致；
- 所有引用 ID 均保留；
- 超预算时可解释删减了什么；
- 长输入不会改变图的有界终止性。

---

## 9. v0.8 — 可靠性、安全与可观测性

### 核心目标

从“可运行”提升到“可长期部署”。

### 实现范围

- structured logging；
- metrics；
- health/readiness checks；
- Provider circuit breaker；
- retry budget；
- per-run cost budget；
- audit log；
- Secret management；
- data retention policy；
- failure injection tests；
- load and concurrency tests；
- 可选 LangSmith exporter，但不作为事实源。

### 验收

- Provider 故障不会形成无限重试；
- 单次任务成本有硬上限；
- 所有外部调用均可审计；
- 日志和 Trace 不包含 Secret；
- 服务重启后任务状态一致；
- 并发任务之间 State 不串扰。

---

## 10. v0.9 — Beta、Shadow Run 与上线演练

### 核心目标

在有限用户和真实任务中验证系统，而不是继续增加架构。

### 实现范围

- Beta feature flag；
- Shadow mode；
- 真实任务采样；
- 用户反馈记录；
- 回退机制；
- runbook；
- 数据备份和恢复演练；
- 安全边界检查；
- 性能和成本优化；
- 发布候选 `v1.0-rc`。

### 验收

- 连续真实任务中无无限循环；
- BLOCKED 和 HUMAN_REVIEW 比例可解释；
- P50/P95 延迟满足预算；
- 回退方案已实际演练；
- 无严重 Evidence 伪造、跨任务污染或 Secret 泄漏；
- 核心功能不依赖 legacy backup 分支。

---

## 11. v1.0 — 半自主上线版本

### 定义

v1.0 是一个半自主研究规划系统：

- 可以接受研究问题和材料；
- 可以自主规划有限检索；
- 可以生成证据综合和方法建议；
- 可以在必要时暂停请求人工判断；
- 可以恢复、追踪、回放和评估；
- 不运行用户代码；
- 不伪造论文、实验和引用；
- 不自动提交或发布论文。

### v1.0 必备条件

- State、Graph、Node、Provider 和 API 合同稳定；
- Checkpoint/HITL 可恢复；
- Evidence 全链路可追溯；
- OOD 和 leakage 测试稳定；
- 成本、延迟和调用次数有硬预算；
- Trace、Eval、回退和运维文档齐全；
- 至少完成一次真实 Beta 验收。

---

## 12. 明确暂缓到 v1.0 之后

以下项目不应阻塞 v1.0：

- Multi-Agent；
- 自动实验执行；
- 自动修改或运行用户仓库；
- 完整论文写作与投稿；
- 长期个人记忆；
- 多租户计费；
- 完整可视化工作台；
- 自动 Prompt 优化；
- 复杂向量数据库和知识图谱；
- 大规模分布式 Worker。

这些能力应在 v1.0 稳定后按实际用户需求单独立项，不提前建设。

## 13. 推荐版本优先级

```text
必须先做：
v0.2 Provider/Retrieval
→ v0.3 Persistence/Trace
→ v0.4 Evaluation
→ v0.5 API/HITL

形成产品能力：
v0.6 Materials Workspace
→ v0.7 ContextBuilder
→ v0.8 Reliability

上线收敛：
v0.9 Beta
→ v1.0 Release
```

## 14. 分支与合并规则

每个版本使用独立分支：

```text
v0.2
v0.3
v0.4
...
v1.0
```

规则：

1. 从最新 `master` 创建；
2. 先提交版本需求和失败测试；
3. 不跨版本提前实现；
4. 通过该版本验收文档后再开 PR；
5. 合并后打标签；
6. 下一版本不得直接基于未合并分支；
7. 破坏性 schema 变更必须提供 migration note；
8. backup legacy 只读，不合并回主线。

## 15. 最近的下一步

v0.1 验收完成后，实际执行顺序应为：

```text
1. 合并并标记 v0.1.0
2. 写 v0.2 REQUIREMENTS.md
3. 写 Provider/Search contract 的失败测试
4. 实现 Fake 和真实 Provider 的共同接口
5. 接入第一个真实 LLM
6. 接入第一个真实 Search Provider
7. 完成真实 happy path 与失败路径验收
8. 合并 v0.2
```

不要在 v0.2 同时建设 Trace UI、Multi-Agent、长期记忆或完整前端。