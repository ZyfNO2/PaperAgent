# TopicPilot-CN 最终技术选型

> 目标：以 AI Agent / RAG / 后端开发实习为导向，完成一个可运行、可部署、可评估的中国研究生开题选题助手。

## 1. 最终技术栈

```text
Python 3.12
├── LangGraph：Agent 状态机与工作流编排
├── FastAPI：后端 API
├── Pydantic v2：结构化输入输出与 Agent State
├── SQLAlchemy 2.x + Alembic：ORM 与数据库迁移
├── PostgreSQL + pgvector：业务数据、证据关系、向量检索
├── Redis + Celery：缓存和异步任务
├── LiteLLM Proxy：统一模型网关
├── Docling：PDF、DOCX 等文档解析
├── GROBID：学术论文元数据与参考文献增强解析
├── BGE-M3：中英文 Embedding
├── BGE-Reranker-v2-M3：检索重排序
├── Langfuse + OpenTelemetry：追踪、评估、可观测性
└── pytest：后端与 Agent 测试

TypeScript
└── Next.js App Router
    ├── React
    ├── Tailwind CSS
    ├── shadcn/ui
    ├── React Flow：状态图与选题退化图
    └── ECharts：风险雷达图与论文趋势图

基础设施
├── Docker Compose
├── MinIO：文件存储
├── Nginx：反向代理
└── GitHub Actions：CI
```

最终可以压缩为一句话：

> **LangGraph + FastAPI + PostgreSQL/pgvector + Redis/Celery + LiteLLM + Docling + BGE + Next.js + Langfuse + Docker Compose。**

---

## 2. 核心框架：LangGraph

### 选择

主流程使用原生 `LangGraph StateGraph`。

TopicPilot-CN 的流程包括：

```text
题目解析
→ 文献/数据集/Baseline 并行检索
→ 证据汇总
→ 航母风险评分
→ 人工确认
→ 选题退化与重新检索
→ 2～3 个工作包设计
→ 开题委员会审查
```

这些流程存在条件分支、循环、人工中断、状态持久化和失败恢复，适合显式状态图，而不是简单的 Prompt Chain。

推荐子图：

```text
LiteratureSearchGraph
DatasetSearchGraph
BaselineSearchGraph
RiskEvaluationGraph
PivotPlanningGraph
WorkPackageGraph
CommitteeReviewGraph
```

### 不作为核心的框架

| 框架 | 结论 | 原因 |
|---|---|---|
| Dify | 仅作快速 Demo | 低代码会削弱 Python、状态机和测试能力展示 |
| AutoGen | 后期可做委员会实验 | 更适合消息驱动和自由多 Agent 对话 |
| AgentScope | 调研项 | 能力完整，但与 LangGraph 主线重复 |
| CrewAI | 不使用 | 角色任务抽象易用，但不如显式状态图适合本项目 |
| LangChain Chain | 不作主流程 | 可使用其模型和 Tool 集成，但主编排交给 LangGraph |

---

## 3. 后端

选择：

```text
FastAPI
Pydantic v2
SQLAlchemy 2.x Async
Alembic
```

Pydantic 同时用于：

- API 请求与响应
- LangGraph State
- LLM Structured Output
- Tool Contract
- 配置和规则校验

核心模型：

```text
TopicSpec
SearchQueryPlan
PaperEvidence
DatasetCandidate
BaselineCandidate
RiskScore
PivotCandidate
WorkPackage
CommitteeReview
FinalReport
```

接口建议：

```text
POST /api/v1/projects
POST /api/v1/projects/{id}/topics/analyze
GET  /api/v1/runs/{run_id}
POST /api/v1/runs/{run_id}/resume
GET  /api/v1/projects/{id}/evidence
POST /api/v1/projects/{id}/pivot/select
GET  /api/v1/projects/{id}/report
```

---

## 4. 数据层

### PostgreSQL + pgvector

第一版只使用 PostgreSQL + pgvector，不同时引入 Qdrant、Milvus、Neo4j 和 Elasticsearch。

PostgreSQL 保存：

```text
项目和用户
Agent Run
论文/数据集/Baseline 元数据
证据关系
风险评分
Pivot 路径
工作包
人工审批
Embedding
全文检索字段
```

### 混合检索

```text
PostgreSQL 全文检索 Top 50
+
pgvector Dense Retrieval Top 50
→ Reciprocal Rank Fusion
→ BGE Reranker
→ Top 5～10 Evidence
```

文档中写作：

> lexical full-text retrieval + dense vector retrieval

不要把 PostgreSQL 全文检索直接称为 BM25。

### 暂不使用

- 独立向量库：MVP 规模没有必要
- Neo4j：先用关系表保存证据关系
- OpenSearch：百万级语料后再考虑

---

## 5. 检索模型

### Embedding

默认使用：

```text
BAAI/bge-m3
```

第一版只使用 Dense Embedding，不同时实现 dense、sparse 和 multi-vector 三套模式。

### Reranker

默认使用：

```text
BAAI/bge-reranker-v2-m3
```

流程：

```text
多路召回 50～100 条
→ Reranker 重排
→ 保留 10～20 条
→ LLM 生成证据摘要
```

开发时可使用 `FlagEmbedding`，部署时拆分成独立 embedding/reranker service。

---

## 6. 模型网关

使用：

```text
LiteLLM Proxy
```

业务代码只调用一个 OpenAI-compatible endpoint，不写死模型品牌。

模型按能力分层：

| 层级 | 任务 |
|---|---|
| Fast Model | 查询扩展、字段抽取、摘要 |
| Strong Model | 风险判断、Pivot、工作包设计 |
| Reviewer Model | 开题委员会和最终审查 |
| Embedding Model | BGE-M3 |
| Reranker Model | BGE-Reranker-v2-M3 |

LiteLLM 负责模型切换、重试、Fallback、预算和调用统计。

---

## 7. 文档解析

### 主解析器：Docling

负责：

- PDF
- DOCX
- PPTX
- HTML
- Markdown
- 表格、标题、阅读顺序和公式

主要用于上传论文、开题报告和学校模板。

### 增强解析器：GROBID

只在需要精细解析学术论文时使用：

- 标题与作者
- 摘要
- 章节
- 引文
- 参考文献
- TEI XML

策略：

```text
普通文档 → Docling
学术论文且需要参考文献 → Docling + GROBID
已有可靠 API 元数据 → 优先使用 API
```

---

## 8. 异步任务

使用：

```text
Redis + Celery
```

Celery 负责：

- 批量文献检索
- PDF 解析
- Embedding
- Reranking
- 报告导出
- 离线评估

边界：

```text
LangGraph：决定下一步做什么
Celery：执行耗时任务
```

LangGraph 节点不要长时间阻塞。

---

## 9. 前端

选择：

```text
Next.js App Router
TypeScript
Tailwind CSS
shadcn/ui
```

不用 Streamlit 作为最终前端。

可视化：

- React Flow：Agent 图、Topic Generalization Graph、证据图
- ECharts：航母风险雷达图、论文趋势、Pivot 前后对比
- SSE：实时展示 Agent 进度

示例进度：

```text
正在拆解题目
正在搜索文献
找到 126 篇候选论文
正在验证数据集
正在计算航母风险
等待用户选择 Pivot
```

---

## 10. 可观测性和评估

### Langfuse

记录：

- Prompt / Completion
- Token 和费用
- 延迟
- Tool 调用
- Agent Trace
- 人工反馈
- 自动评价

### OpenTelemetry

贯通：

```text
FastAPI Request
→ LangGraph Run
→ Celery Task
→ External API
→ PostgreSQL
→ LLM
```

### Evals

```text
topic_parse_eval
query_expansion_eval
dataset_discovery_eval
baseline_discovery_eval
risk_classification_eval
pivot_quality_eval
work_package_eval
citation_grounding_eval
```

核心指标：

```text
Evidence Precision
Dataset Recall@K
Baseline Recall@K
Unsafe Pass Rate
Pivot Acceptance Rate
Citation Hallucination Rate
Workflow Success Rate
Average Latency
Average Cost
```

---

## 11. 测试

后端：

```text
pytest
pytest-asyncio
httpx
testcontainers
coverage
```

前端：

```text
Vitest
React Testing Library
Playwright
```

至少完成一个端到端测试：

```text
创建项目
→ 输入题目
→ 获取风险结果
→ 选择 Pivot
→ 生成工作包
→ 下载报告
```

---

## 12. 部署

Docker Compose 服务：

```text
nginx
web
api
worker
postgres
redis
minio
litellm
langfuse
grobid
```

Docling 先作为 Worker Python 依赖。

第一版不使用 Kubernetes。核心 Agent、RAG 和评估完整度比复杂部署更重要。

---

## 13. 推荐仓库结构

```text
topicpilot-cn/
├── apps/
│   ├── api/
│   ├── worker/
│   └── web/
├── packages/
│   ├── agents/
│   │   ├── graphs/
│   │   ├── nodes/
│   │   ├── states/
│   │   ├── prompts/
│   │   └── tools/
│   ├── retrieval/
│   ├── documents/
│   ├── evidence/
│   ├── domain/
│   ├── db/
│   └── evals/
├── tests/
├── infra/
├── scripts/
├── docs/
├── pyproject.toml
├── uv.lock
└── README.md
```

---

## 14. 分阶段实施

### P0：最小 Demo

```text
LangGraph + FastAPI + Pydantic + SQLite
```

完成题目输入、三个节点和风险报告，控制在 3～5 天。

### P1：实习作品 MVP

```text
LangGraph
FastAPI
PostgreSQL + pgvector
Redis + Celery
LiteLLM
OpenAlex / Semantic Scholar / GitHub / Hugging Face
Docling
Next.js
Docker Compose
```

### P2：工程增强

```text
BGE-M3
Reranker
GROBID
MinIO
Langfuse
OpenTelemetry
React Flow
ECharts
自动评估
```

### P3：只选一个加分项

```text
A. 开题委员会多 Agent 辩论
B. 学校开题模板适配
C. 中文文献 RIS/BibTeX 导入
D. DOCX 报告导出
E. 历史开题题目评估数据集
```

---

## 15. 技术取舍清单

### 必须使用

| 技术 | 目的 |
|---|---|
| LangGraph | Agent 状态机 |
| FastAPI + Pydantic | 后端和结构化数据 |
| PostgreSQL + pgvector | 业务、关系和向量 |
| Redis + Celery | 异步任务 |
| LiteLLM | 统一模型网关 |
| Docling | 文档解析 |
| Next.js + TypeScript | 完整产品 |
| Langfuse | Agent 追踪与评估 |
| Docker Compose | 一键部署 |

### 暂不使用

| 技术 | 原因 |
|---|---|
| Dify 作为核心 | 代码能力展示不足 |
| AutoGen 作为核心 | 自由多 Agent 对话不是主问题 |
| CrewAI | 与 LangGraph 重叠 |
| Qdrant / Milvus | MVP 无需独立向量库 |
| Neo4j | PostgreSQL 关系表已足够 |
| Elasticsearch / OpenSearch | 初期规模不足 |
| Kubernetes | 偏离核心开发 |
| LLM 微调 | 不是第一版重点 |
| Streamlit 最终前端 | 产品能力展示不足 |

---

## 16. 面试表述

> 项目的主流程不是简单 ReAct，而是包含并行检索、条件分支、人工审批和失败重试的长状态工作流，因此我选择 LangGraph StateGraph 作为编排层。后端使用 FastAPI 和 Pydantic 定义 Agent State 与 Tool Contract，PostgreSQL 同时保存项目数据、证据关系和 pgvector 向量。耗时的文档解析与批量检索通过 Celery 异步执行，模型调用统一经过 LiteLLM。检索采用全文召回、向量召回和 Reranker 的三阶段架构，所有 LLM 调用和节点执行通过 Langfuse 与 OpenTelemetry 追踪。前端使用 Next.js 展示执行状态、证据图和选题风险。

---

## 17. 实施重点

```text
LangGraph 做深
而不是同时学多个 Agent 框架

PostgreSQL + pgvector 做完整
而不是堆多个数据库

FastAPI + Next.js 做成产品
而不是停留在 Notebook

Langfuse + Evals 做出评估
而不是只展示一次成功 Demo
```

---

## 18. 官方资料

- [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)
- [FastAPI](https://fastapi.tiangolo.com/)
- [pgvector](https://github.com/pgvector/pgvector)
- [Next.js App Router](https://nextjs.org/docs/app)
- [LiteLLM](https://docs.litellm.ai/docs/)
- [Docling](https://docling-project.github.io/docling/)
- [GROBID](https://grobid.readthedocs.io/)
- [Celery](https://docs.celeryq.dev/)
- [Langfuse](https://langfuse.com/docs)
- [OpenTelemetry](https://opentelemetry.io/docs/languages/python/)
- [BGE-M3](https://huggingface.co/BAAI/bge-m3)
- [BGE-Reranker-v2-M3](https://huggingface.co/BAAI/bge-reranker-v2-m3)
