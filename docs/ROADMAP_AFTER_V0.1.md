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

长期目标是形成一个可在网页端和小程序端使用、可暂停、可恢复、可审计的研究规划 Agent，而不是一次性自动写论文的黑箱系统。

## 2. 路线图调整原因

经过 PrismLens、AutoResearchClaw、PaperQA2、STORM / Co-STORM 和 ResearchPilot 的对比，后续版本顺序调整为：

```text
先把文献检索做对
→ 再把长任务做成可恢复 API
→ 再建立检索质量评估
→ 再做 Web/PWA/小程序外壳
```

主要减法：

- v0.2 不引入 Multi-Agent；
- v0.2 不引入向量数据库；
- v0.2 不解析全部 PDF；
- v0.2 不做每篇论文 LLM Judge；
- v0.3 默认不要求 Redis + PostgreSQL + 独立 Worker；
- v0.5 小程序只做任务、结果和人工审核，不复制完整桌面工作台。

详细检索方案见：

- [v0.2 文献检索与 Web-First 上线方案](planning/V0.2_LITERATURE_RETRIEVAL.md)

## 3. v0.1 完成后的立即工作

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

## 4. v0.2 — 文献检索核心与真实 Provider

### 核心目标

把 v0.1 Retrieval Subgraph 接入真实学术来源，建立可信、可缓存、可解释的 Evidence Bundle，同时保持顶层 Graph 不变。

### Graph 兼容

```text
prepare_search_node
  └─ QueryPlanner + SourceRouter

search_tool_node
  └─ Provider Fan-out + Normalize + Deduplicate/Merge

verify_evidence_node
  └─ Metadata Verify + Rank + Coverage Audit

retrieval_gate
  └─ enough | retry_under_budget | budget_exhausted
```

### 实现范围

- `LLMProvider` 正式结构化接口；
- `LiteratureProvider` 统一接口；
- OpenAlex 作为默认广覆盖来源；
- Semantic Scholar 和 arXiv 作为补充来源；
- Crossref / DataCite DOI 验证；
- Query Lane 与 Evidence Gap 绑定；
- 来源并发、独立限流和总 deadline；
- ProviderResult 区分 success / empty / timeout / rate_limited / failed；
- DOI → arXiv ID → canonical ID → title/year/author 去重；
- 多来源元数据合并和 provenance；
- 可解释相关性、覆盖率和多样性排序；
- 最多一次定向补搜；
- 成功缓存、短期负缓存和 verification cache；
- 真实 Provider smoke test，默认不进入普通离线 CI。

### 调用预算

```text
Query lanes: 2—4
Retrieval rounds: <= 2
Discovery providers per lane: <= 2
Results per provider request: <= 10
Merged candidates: <= 30
Final paper cards: <= 12
LLM calls inside retrieval: <= 2
```

### 暂不实现

- Qdrant / Elasticsearch；
- 全量 PDF 下载和解析；
- Citation Graph 无限扩展；
- Google Scholar 爬虫；
- Multi-Agent 文献辩论；
- 每篇论文单独 LLM 评分；
- 自动 Related Work 全文写作；
- GitHub / 网页 / 数据集与论文混合排序。

### TDD 重点

- Provider 失败不能伪装成真实空结果；
- 故障产生的空列表不能污染正常缓存；
- 同一论文跨来源正确合并；
- 预印本和正式出版版本正确关联；
- 高引用但不相关论文不能压过相关论文；
- 新论文无引用时仍可进入结果；
- required gap 不得被 LLM 删除；
- 全部来源失败时明确 BLOCKED；
- 部分来源失败时返回 partial result 和失败状态。

### 验收

- 至少两个真实学术来源可运行；
- 至少一种 DOI / arXiv 验证路径可运行；
- 检索循环最多两轮；
- Retrieval 内 LLM 调用最多两次；
- 去重后保留全部来源 provenance；
- rejected / failed verification 不支持最终 claim；
- Citation Count 不是唯一或主要排序；
- 无来源时明确 BLOCKED，不补造文献；
- Fake Provider 离线测试与真实 Smoke Test 分开报告。

---

## 5. v0.3 — Durable Task API、Checkpoint 与进度传输

### 核心目标

让检索和研究任务可以从网页端发起，在后台运行，并支持查询、取消、暂停、恢复和审计。

### 默认最小部署

```text
FastAPI
+ SQLite
+ LangGraph Checkpointer
+ 单进程后台 Task Runner
+ SSE for Web
+ Polling fallback for Mini Program
```

只有实际出现多实例或高并发需求后，才升级为：

```text
Redis + ARQ/RQ/Celery
PostgreSQL
独立 Worker
```

### 实现范围

- 创建 task / run；
- 查询状态和阶段进度；
- 获取论文分页结果；
- cancel；
- Human review 提交；
- 幂等 request key；
- SQLite Checkpointer；
- run / thread / session 合同；
- versioned `TraceEvent`；
- payload redaction；
- SSE 事件；
- Polling API；
- recorded replay；
- Checkpoint schema migration 最小机制。

### 状态机

```text
created
→ queued
→ running
→ waiting_for_human
→ running
→ completed | partial | blocked | failed | cancelled
```

### 借鉴来源

- PrismLens：FastAPI、后台任务、SSE、认证和前后端分层；
- PaperClaw：Session、Trace、Safe Resume、Recorded Replay；
- ResearchPilot：实时阶段进度和报告查询。

### 减法

- 不先引入 Redis；
- 不先引入 PostgreSQL；
- 不做完整 Trace UI；
- 不做团队协作；
- 不做多租户计费；
- 不做 WebSocket，SSE + Polling 足够。

### TDD 重点

- POST 快速返回 task_id；
- 重复幂等键不重复执行任务；
- cancel 后不再产生新的 Provider 调用；
- resume 不重复执行已经完成的搜索请求；
- SSE 与 Polling 暴露相同权威状态；
- replay 不调用真实模型和工具；
- Secret 不进入 Trace 和数据库。

### 验收

- 任意顶层节点后可恢复；
- 网页断开后任务继续执行；
- 小程序只靠轮询也能完整查看状态；
- Human review 可跨进程恢复；
- Trace 完整率 100%；
- Checkpoint 损坏时显式失败，不静默重置。

---

## 6. v0.4 — 文献检索与 Evidence 自动评估

### 核心目标

建立可重复的检索质量基线，不再依赖“结果看起来不错”。

### 实现范围

- Provider availability / partial failure 指标；
- duplicate collapse accuracy；
- metadata merge accuracy；
- verification precision；
- Evidence Gap coverage；
- source diversity；
- year / type constraint compliance；
- relevance ranking test；
- unsupported claim detection；
- retry / tool failure 指标；
- Token、成本、P50/P95 延迟；
- OOD 测试集；
- legacy entity leakage scanner；
- golden Evidence Bundle；
- golden Trace；
- regression report；
- 可选 LLM reviewer 实验，但不得覆盖硬规则。

### 测试集结构

至少覆盖：

- CV；
- NLP；
- 推荐系统；
- 时间序列；
- 数据库；
- 软件工程；
- 跨学科问题；
- 非英语查询；
- 信息不足问题；
- 不可完成问题；
- 恶意诱导伪造引用的问题；
- 只有预印本的新方向；
- 同一论文多版本和多来源记录。

### 验收

- 每次版本提交可生成确定性评估报告；
- 所有 claim 可追溯到 Evidence 或标记 proposed / inferred；
- OOD 任务无固定案例污染；
- 真实 Provider 指标与 Fake Provider 指标分开；
- Mock 结果不得称为真实 E2E；
- 排序回归和去重回归可以自动发现。

---

## 7. v0.5 — Web/PWA 与小程序壳

### 核心目标

将已经稳定的 Retrieval + Task API 做成最小可用产品，不在前端重建 Agent 逻辑。

### Web / PWA

- 登录；
- 创建研究任务；
- 查看阶段和进度；
- 论文卡片分页；
- Evidence Gap 标签；
- verified / pending / suspicious / failed 标记；
- 接受、拒绝、收藏；
- 查看来源和验证方法；
- 导出 Markdown / JSON / BibTeX；
- 历史任务。

### 小程序

只提供：

- 创建任务；
- 轮询任务；
- 查看论文卡片；
- 接受 / 拒绝；
- 查看最终摘要；
- 分享任务链接。

不提供：

- 完整 PDF 阅读；
- Prompt 配置；
- Trace 调试；
- 复杂图表；
- Provider 管理；
- 大段长文编辑。

### 技术建议

- Web 优先 Next.js PWA；
- 小程序使用同一 REST API；
- Web 使用 SSE，小程序使用 Polling；
- 论文列表分页；
- 首屏只返回元数据和短摘要；
- 全文和长摘要按需加载；
- 单次状态响应建议不超过 200 KB。

### 验收

- 手机和桌面均能完成创建、查看和审核；
- 前端刷新不丢任务；
- 小程序断网恢复后可继续查询；
- 用户操作不会直接修改未经 API 校验的 State；
- 前端不接触 Provider Secret；
- P50/P95 交互延迟满足预算。

---

## 8. v0.6 — 研究材料工作区

### 核心目标

让用户上传材料成为一等 Evidence，而不是附加文本。

### 实现范围

- 用户上传材料登记；
- PDF、Markdown、纯文本基础解析；
- source provenance；
- 文档 chunk 和稳定 ID；
- 用户材料与网络材料统一 Evidence contract；
- 冲突来源标记；
- accepted / rejected 人工操作；
- 报告导出；
- 暂不运行用户代码。

### TDD 重点

- 同一文档重复上传去重；
- chunk ID 稳定；
- 材料删除后引用失效可检测；
- 用户材料优先级不等于真实性；
- PDF 解析失败不得伪造正文。

### 验收

- 用户材料可进入检索、综合、方法设计和最终报告；
- 每个引用可回到原文件和位置；
- 冲突来源不会被静默合并；
- 解析失败有明确状态。

---

## 9. v0.7 — ContextBuilder 与上下文预算

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

### 验收

- Workflow 不直接读取完整 State；
- 压缩前后 required constraints 一致；
- 所有引用 ID 保留；
- 超预算时可解释删减内容；
- 长输入不改变图的有界终止性。

---

## 10. v0.8 — 可靠性、安全与可观测性

### 核心目标

从“可运行”提升到“可长期部署”。

### 实现范围

- structured logging；
- metrics；
- health / readiness；
- Provider circuit breaker；
- retry budget；
- per-run cost budget；
- audit log；
- Secret management；
- data retention policy；
- failure injection tests；
- load and concurrency tests；
- Redis / PostgreSQL / 独立 Worker 升级评估；
- 可选 LangSmith exporter，但不作为事实源。

### 验收

- Provider 故障不会形成无限重试；
- 单次任务成本有硬上限；
- 所有外部调用可审计；
- 日志和 Trace 不含 Secret；
- 服务重启后任务状态一致；
- 并发任务之间 State 不串扰。

---

## 11. v0.9 — Beta、Shadow Run 与上线演练

### 核心目标

在有限用户和真实任务中验证系统，而不是继续增加架构。

### 实现范围

- Beta feature flag；
- Shadow mode；
- 真实任务采样；
- 用户反馈；
- 回退机制；
- runbook；
- 数据备份和恢复演练；
- 安全边界检查；
- 性能和成本优化；
- 发布候选 `v1.0-rc`。

### 验收

- 连续真实任务无无限循环；
- BLOCKED、PARTIAL 和 HUMAN_REVIEW 比例可解释；
- P50/P95 延迟满足预算；
- 回退方案实际演练；
- 无严重 Evidence 伪造、跨任务污染或 Secret 泄漏；
- 核心功能不依赖 legacy backup 分支。

---

## 12. v1.0 — 半自主上线版本

### 定义

v1.0 是一个网页端优先、可被小程序调用的半自主研究规划系统：

- 可以接受研究问题和材料；
- 可以自主规划有限文献检索；
- 可以生成证据综合和方法建议；
- 可以在必要时暂停请求人工判断；
- 可以恢复、追踪、回放和评估；
- 不运行用户代码；
- 不伪造论文、实验和引用；
- 不自动提交或发布论文。

### v1.0 必备条件

- State、Graph、Node、Provider 和 API 合同稳定；
- Checkpoint / HITL 可恢复；
- Evidence 全链路可追溯；
- OOD 和 leakage 测试稳定；
- 成本、延迟和调用次数有硬预算；
- Web 和小程序核心流程可用；
- Trace、Eval、回退和运维文档齐全；
- 至少完成一次真实 Beta 验收。

---

## 13. 明确暂缓到 v1.0 之后

以下项目不应阻塞 v1.0：

- Multi-Agent；
- 自动实验执行；
- 自动修改或运行用户仓库；
- 完整论文写作与投稿；
- 长期个人记忆；
- 多租户计费；
- 完整可视化科研工作台；
- 自动 Prompt 优化；
- 大规模向量数据库和知识图谱；
- 大规模分布式 Worker；
- Citation Graph 全局爬取。

## 14. 推荐版本优先级

```text
检索基础：
v0.2 Literature Retrieval Core

产品运行基础：
v0.3 Durable Task API / Checkpoint / SSE / Polling

质量基础：
v0.4 Retrieval and Evidence Evaluation

用户入口：
v0.5 Web/PWA and Mini Program Shell

能力扩展：
v0.6 Materials Workspace
→ v0.7 ContextBuilder
→ v0.8 Reliability

上线收敛：
v0.9 Beta
→ v1.0 Release
```

## 15. 分支与合并规则

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

## 16. 最近的下一步

v0.1 验收完成后，实际执行顺序应为：

```text
1. 合并并标记 v0.1.0
2. 从 master 创建 v0.2
3. 写 v0.2 REQUIREMENTS.md 和固定 Provider Fixtures
4. 写 ProviderResult / PaperRecord / CoverageReport 失败测试
5. 实现 OpenAlex Provider
6. 实现 Semantic Scholar / arXiv Provider
7. 实现去重、元数据合并和 provenance
8. 实现 Crossref / DataCite 验证
9. 实现可解释排序和 Coverage Gate
10. 完成真实 Smoke Test 与检索评估
11. 合并 v0.2
```

不要在 v0.2 同时建设完整前端、Multi-Agent、长期记忆、Qdrant 或全量 PDF RAG。
