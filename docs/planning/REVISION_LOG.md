# PaperAgent Planning Revision Log

## 2026-07-16 — v0.2 文献检索与 Web-First 路线调整

### 状态

- 适用范围：`v0.2+`
- 当前开发版本：`v0.1`
- `v0.1` Graph、Node、State、TDD Fixtures 和验收合同：不修改

### 本次冻结的决策

1. v0.2 优先建设可信文献检索核心，不提前建设完整前端。
2. 保持 v0.1 顶层 LangGraph 不变，只增强 Retrieval Subgraph 内部服务。
3. 学术发现源优先采用 OpenAlex、Semantic Scholar 和 arXiv。
4. DOI 和出版元数据验证采用 Crossref / DataCite。
5. Provider 状态必须区分 `success`、`empty`、`rate_limited`、`timeout` 和 `failed`。
6. 去重优先使用 DOI、arXiv ID、Provider Canonical ID，再使用标题、年份和作者。
7. 重复记录必须合并多来源 Metadata 与 Provenance，不能只保留引用量较高的一条。
8. 排序以相关性、Evidence Gap 覆盖、验证状态、时效和多样性为主；Citation Count 只能作为弱特征。
9. Retrieval 内最多两次 LLM 调用，检索循环最多两轮。
10. v0.3 默认使用 FastAPI、SQLite、LangGraph Checkpointer、SSE 和 Polling；不提前强制 Redis、PostgreSQL 和独立 Worker。
11. v0.5 Web 优先采用 PWA，小程序只保留任务创建、状态查询、论文卡片和人工审核。
12. Multi-Agent、全量 PDF RAG、Qdrant、Citation Graph 全局扩展和自动论文写作延后。

### 参考项目结论

- PrismLens：借鉴 FastAPI、后台任务、SSE、Checkpoint 和前后端分层；不照搬固定媒体立场查询和 Tavily-only 检索。
- AutoResearchClaw：借鉴多源检索、缓存、标识符去重和引用验证；重写并发、元数据合并、排序和错误状态。
- PaperQA2：借鉴 Evidence Gathering 与元数据感知；v0.2 不搬入全量 PDF、Embedding 和 Vector DB。
- STORM / Co-STORM：借鉴多角度 Query Lane 和缺口追问；不搬入多专家长对话。
- ResearchPilot：借鉴 FastAPI + SSE + Next.js 的轻量产品体验；不提前采用四 Agent 和 Qdrant。

### 关联文档

- `docs/ROADMAP_AFTER_V0.1.md`
- `docs/planning/V0.2_LITERATURE_RETRIEVAL.md`

### 合并规则

该规划记录随 `v0.1` 分支保存，但不代表在 v0.1 中实现 v0.2 功能。v0.1 完成验收并合并到 `master` 后，必须从最新 `master` 新建 `v0.2` 分支，再根据上述合同执行 TDD 开发。
