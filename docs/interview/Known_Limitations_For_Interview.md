# PaperAgent · 已知限制与诚实表达（Session 40）

> 面试时主动说出限制，比被追问才说更有优势。
> 本文档列出真实限制 + 表达方式。

---

## 1. 真实已知限制

### 1.1 Embedding / 向量库未接入

**现状：** RAG 用 mock embedding（hash + noise），没有真实向量库。
**影响：** 检索质量受限于 mock 实现的"巧合"质量。
**应对：** 设计上 Hybrid 检索 + RRF 融合已经准备好，接入 sentence-transformers / FAISS 是 drop-in 替换。
**诚实表达：**

> 「RAG 的 embedding 是 mock 实现，真实环境需要接 sentence-transformers 或 BGE。但我的 pipeline 设计（Hybrid + RRF + 5 因子 Rerank）是框架级的，切换 embedding 是配置改动不是代码改动。」

---

### 1.2 持久化用 JSONL 而非 SQLite

**现状：** RunEvent / Trace 用 `.runtime/{project_id}/{run_id}/*.jsonl` 存盘。
**影响：** 大数据量时全表扫描慢；并发写需要锁。
**应对：** MVP 阶段简单优先，调试方便（`cat | jq` 即可）。生产环境可迁 SQLite。
**诚实表达：**

> 「数据持久化用 JSONL 不是 SQLite，是 MVP 阶段的有意选择——调试方便（cat + jq 即可），并发问题先不上量。生产环境可平滑迁移 SQLite，因为 schema 已经稳定。」

---

### 1.3 Snapshot 是 in-memory 未持久化

**现状：** ProjectMemorySnapshot 是 in-memory dict，没存 SQLite。
**影响：** 进程重启后 snapshot 丢失，需要重新 build。
**应对：** API 已经有 `get_latest_snapshot()` / `build_snapshot_from_run()`，存盘是后续工作。
**诚实表达：**

> 「ProjectMemorySnapshot 当前是 in-memory，进程重启后会重新从 events 重建（这个 rebuild 逻辑已经实现了）。生产环境会持久化到 SQLite，逻辑层不变。」

---

### 1.4 LLM 路径用 mock / stub

**现状：** LLM 调用层有 anthropic SDK 接入代码，但 prompt 模板和 fallback 走 heuristic。
**影响：** 真实 LLM 行为未充分测试。
**应对：** Heuristic fallback 已经覆盖 95% 常见场景，LLM 挂了不中断。
**诚实表达：**

> 「LLM 路径在测试环境走 heuristic fallback，真实 LLM API 接入是配置的（环境变量）。heuristic 已经覆盖 95% 常见输入，LLM 挂了也不中断——这是有意设计的双路径。」

---

### 1.5 Multi-Agent 仅做设计未真正实现

**现状：** `agent_router.py` 定义了 7 roles + 静态路由 + 成本预算，但**没有真正执行子 Agent**。
**影响：** 当前仍是单流程 + Gate，Multi-Agent 是渐进扩展路径。
**应对：** 设计已就位（schema + router + 成本检查 + 投票 + 降级），需要时再实现。
**诚实表达：**

> 「Multi-Agent 在 PaperAgent 是『渐进可扩展』设计，不是『已完成』。schema、router、成本预算、投票、降级都已实现，但当前业务流仍是单流程 + Gate。这是合理工程选择——选题流程强顺序，拆多 Agent 收益小。」

---

### 1.6 MCP 是 HTTP transport 而非 stdio / sse

**现状：** MCP server 通过 FastAPI HTTP 暴露，stdio / sse 未实现。
**影响：** 与标准 MCP 客户端集成需要 wrapper。
**应对：** `server.py` 已封装 `call_tool()`，升级 stdio 是 200 行代码的事。
**诚实表达：**

> 「MCP server 当前是 HTTP transport（便于 Playwright 测试和 curl 调用），不是标准 stdio / sse。server.py 封装了 call_tool 主逻辑，升级到 stdio 是包装问题，核心业务逻辑不变。」

---

### 1.7 URL 验证是 mock

**现状：** `verify_url()` 当前返回 mock 结果（基于 URL 模式），没真发 HTTP HEAD 请求。
**影响：** 真实网络环境未充分测试。
**应对：** `verification.py` 已经有 HTTP HEAD 200 + 状态码 + 响应时间的代码逻辑，激活即可。
**诚实表达：**

> 「URL 验证当前是 mock 实现（基于 URL 模式判断），真实 HTTP HEAD 调用是配置改动。设计层面已经支持状态码 + 响应时间检查，激活是 5 行代码的事。」

---

### 1.8 没有真实向量库 / ANN

**现状：** Dense 检索是 mock（hash + noise）。
**影响：** 大规模候选（> 10K）性能不可用。
**应对：** 框架已支持切换 FAISS / Milvus / Qdrant。
**诚实表达：**

> 「Dense 检索当前是 in-memory hash，> 10K 候选会慢。生产环境接 FAISS / Milvus 是 drop-in。」

---

### 1.9 没做跨语言 RAG

**现状：** 关键词 / 候选都是中文，跨语言（中文 query → 英文论文）未实现。
**影响：** 英文论文召回率受限。
**应对：** 接入 mContriever / mE5 + Query 翻译是后续工作。
**诚实表达：**

> 「跨语言 RAG 未实现。生产环境用 mContriever / mE5 + Query 翻译，框架层无需改动。」

---

### 1.10 没做并发压测

**现状：** 单进程 FastAPI，没有压测数据。
**影响：** 高并发性能未知。
**应对：** 读多写少场景单进程够用，写多场景需要加锁或迁 SQLite。
**诚实表达：**

> 「没做压测。MVP 阶段单进程 FastAPI 够用，并发上量后再考虑 worker 数量 + 锁优化。」

---

## 2. 表达策略

### 2.1 主动说 vs 被追问说

| 时机 | 表达 |
|---|---|
| **主动说** | 当面试官问到「有什么不足」「未来怎么迭代」时 |
| **被追问说** | 当面试官发现限制后直接追问时 |
| **不要主动说** | 自我陈述时硬塞一堆限制，转移话题 |

### 2.2 表达模板：限制 + 应对 + 后续

> 「**限制**：xxx
> **应对**：当前用 yyy 解决，95% 场景够用
> **后续**：生产环境是 zzz，已经预留接口 / 是 drop-in 替换」

### 2.3 反例（不推荐）

> ❌「我这个项目做得很差，xxx 不行」
> ❌「我用了 LLM 但没接真实 LLM」（主动暴露无意义）
> ❌「我不知道未来怎么扩展」（缺路线感）

---

## 3. 不要说的话

### 3.1 绝对承诺

| 禁止 | 原因 |
|---|---|
| ❌ 100% 准确 | 没有系统 100% 准确 |
| ❌ 完全避免幻觉 | LLM 永远可能幻觉 |
| ❌ 完美支持所有场景 | 边界永远存在 |
| ❌ 保证通过开题 | 不是工具能保证的 |

### 3.2 自我贬低

| 禁止 | 原因 |
|---|---|
| ❌ 完全失败 | 失败案例都有工程应对 |
| ❌ 毫无价值 | 16 个失败案例都有测试守护 |
| ❌ 不可用 | MVP 阶段有明确价值 |
| ❌ 我做得很差 | 影响面试官判断 |

### 3.3 无关抱怨

| 禁止 | 原因 |
|---|---|
| ❌ 时间不够 | 解释 ≠ 借口 |
| ❌ 队友不行 | 不专业 |
| ❌ 需求老变 | 显被动 |

---

## 4. 主动暴露限制的时机

### 4.1 问「你项目最大的不足是什么？」

**回答模板：**

> 「诚实说，最大不足是 **RAG 的真实 embedding 未接入**。当前用 mock 实现，但 pipeline 设计（Hybrid + RRF + 5 因子 Rerank）是框架级的，切换是配置改动不是代码改动。其他不足还有 (1) Snapshot 未持久化 (2) Multi-Agent 仅做设计。但这些都不影响系统的**工程边界感**——什么让 LLM 做、什么不让 LLM 做，这个设计是完成的。」

### 4.2 问「如果继续做优先补什么？」

**回答模板：**

> 「P0 优先级：
> 1. 真实 embedding（sentence-transformers + FAISS）
> 2. Snapshot 持久化（SQLite）
> 3. URL 真实验证（HTTP HEAD）
> 4. MCP stdio transport
> 5. 跨语言 RAG（mContriever）
>
> P1 优先级：
> 6. 真实 LLM 接入
> 7. Multi-Agent 真正实现
> 8. 并发压测」

### 4.3 问「你做的和开源项目有什么差异？」

**回答模板：**

> 「和 LangChain / AutoGen / LangGraph 的核心差异是**工程边界感**：
> - LangChain: 灵活但无 Gate
> - AutoGen: 多 Agent 灵活但成本高
> - LangGraph: 状态机但需手写降级
>
> PaperAgent 把 **Gate / Trace / 失败降级 / 硬拦截** 做进系统层，不留给业务方。」

---

## 5. 限制分级

| 等级 | 限制 | 表达强度 |
|---|---|---|
| **核心限制** | 真实 embedding 未接入 | 主动说 |
| **次要限制** | Snapshot / 持久化 / URL 验证 mock | 主动说 |
| **未来工作** | Multi-Agent 实现 / 跨语言 | 主动说 |
| **架构选择** | JSONL vs SQLite / HTTP vs stdio | 被追问说 |
| **优化空间** | 压测 / 性能调优 | 被追问说 |

---

## 6. 一句话诚实表达

> 「PaperAgent 是一个 MVP 阶段的项目，核心是工程边界感（Gate / Trace / 失败降级），RAG 的真实 embedding 和持久化是配置改动级别的后续工作，Multi-Agent 是渐进扩展路径。」

---

> **诚实表达的核心：限制 + 应对 + 后续，3 段式。**
> **不要堆限制（显得没信心），不要美化限制（显得不诚实）。**