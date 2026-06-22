# PaperAgent RAG「专业数据库」升级设计（求职向，design-only）

> 日期：2026-06-23
> 性质：设计稿（design-only），不是 SOP / Phase收。
>发：小红书一面反思点 #1 —「做 RAG统时，把文档弄复杂一些，用上专业数据库，而不是简单文档、没有复杂召回策略」。本稿用 PaperAgent现有结构给出可演进到「企业级 RAG」的最小路径，思路为主，落地与否以代码 + pytest 为准。
> 口径：守三档（implemented / lightweight / design-only）。当前 PaperAgent RAG = lightweight（query解 +选召回 + 单层 URL Verified + Evidence升）。本稿给出从 lightweight →近企业级的 design-only图。

---

## 0.状诚实盘点（与面试官讲法对照）

### 0.1 当前已实现的 RAG路（lightweight）
- Query解：`query → keyword gate → SearchQueryPlan`（7检索层）
- 多源召回：OpenAlex / arXiv / GitHub / HuggingFace（Session 14）
-选结构：`CandidateResource`（含来源、置信、raw metadata）
- 证据晋升：`Candidate → EvidenceRef` 单层 URL Verified（arxiv/github/huggingface/kaggle/generic_url，confidence 0.0–0.85）
- 评估：Session 17 baseline + Web Playwright E2E（test_session34_rag_eval）

### 0.2试官会立刻指出「太简单」的三个缺口
1.有专业向量库（只有内存字典/文件索引）
2.有复杂召回策略（只有单路召回，没有 Hybrid Search + Rerank）
3. 没有 RAG 评估闭环（只有 baseline中率，没有 Recall@K / MRR / Citation Coverage / Evidence Precision）

本稿把这三块一次性补全到「能在面试里讲清企业级取舍」的程度。

---

## 1.级蓝图：Modular RAG Pipeline（对应企业「可插拔组件」面试点）

把现在的线性召回重构成可插拔管线，对齐 LangChain / Haystack / LlamaIndex 的 Retriever/Reranker/Verifier/Reporter口划分：

```
Query
  → QueryPlanner（已实现，扩 Hybrid mode）
  → Retriever（可插拔：BM25Retriever / DenseRetriever / GraphRetriever）
  → Fusion（RRF Reciprocal Rank Fusion合多路）
  → Reranker（CrossEncoder / LLM Rerank）
  → Verifier（多层验证链，见下）
  → Reporter（CandidateResource + EvidenceRef，已实现）
  → Eval（Recall@K / MRR / Citation Coverage / Evidence Precision）
```

企业级对标：Haystack Pipeline / LangChain RunnablePassthrough / LlamaIndex QueryEngine。讲法是「我没有把 RAG 写成一个检索函数，而是 Retriever/Reranker/Verifier/Reporter 四段可插拔接口，对标 Haystack Pipeline」。

## 2. 专业数据库选型（不引重依赖到 MVP，但讲清取舍）

### 2.1 向量库选型对照表（design-only，选一个作为扩展位）

| 向量库 | 为什么讲它 | 小型化取舍 |
|---|---|---|
| Qdrant | Rust 实现，gRPC/REST，过滤强，生产级；对标企业「向量检索服务」 | 当前不接，留 `DenseRetriever`口，本地用 FAISS/纯 numpy 占位 |
| Chroma | 开发友好，嵌入式，适合 MVP | 可作为 lightweight认盘 |
| pgvector |用 Postgres，企业已有 DBA 时最省 | 不引（项目无 PG 依赖） |
| Milvus | 分布式、十亿级 | 不引（过重） |

口径：当前 lightweight 用内存/FAISS 占位；design-only留 Qdrant 适配层。讲法是「我选 Qdrant 作为生产扩展位，本地用 FAISS 占位，接口隔离，不锁死存储」。


### 2.2 Hybrid Search（BM25 + Dense）—小红书场核心加分项
- BM25（关键词稀疏检索）：`rankank25` 或纯 Python 实现；复用已有的 SearchQueryPlan 关键词。
- Dense（语义向量）：本地 bge-small / m3e型或 API embedding；FAISS 占位索引。
-合：RRF（Reciprocal Rank Fusion），`score = Σ 1/(k+rank_i)`，k=60。**不学加性 fusion**（不同源量纲不同易翻车），RRF 是工业默认。
- 企业对标：Elasticsearch Hybrid Search 的 BM25 + kNN。讲法「我用 RRF合 BM25 和 Dense，对标 ES Hybrid，不用加性融合避免量纲问题」。

### 2.3 Rerank（CrossEncoder / LLM Rerank）
- CrossEncoder：bge-reranker-base，输入 (query, doc)出相关性分；比 bi-encoder但慢，只对 top-K 用（K=20）。
- LLM Rerank（可选）：让 LLM打分，复用已有 PromptProtocol；守「LLM 只判相关性不入 supports」不变式（对应 AutoResearchClaw §3.2 Layer4）。
- 企业对标 Cohere Rerank / Jina Reranker。
-法「Retriever 快粗召回 top-50，Reranker CrossEncoder排到 top-10，成本和精度的经典 trade-off」。

## 3.杂召回策略（从单路 →多路 + Graph）

### 3.1 多源多路并行召回 + RRF合
当前 Session 14 已经有多源（OpenAlex/arXiv/GitHub/HF），但是「并列列表」不是「融合排序」。升级：
-源一路 Retriever，并行召回 top-N，RRF合成统一候选池。
-败熔断（对接 AutoResearchClaw §3.3 显式熔断 closed/half_open/open + 数退避）。
- 企业对标 Resilience4j / Sentinel 的 circuit breaker。

### 3.2 多跳检索 / GraphRAG局部查询（对应 §14 PaperKG）
- 单跳：focus paper → references/cited_by（OpenAlex/arXiv 已有 metadata）。
- 多跳：`contradicts` / `extends` / `uses_same_dataset` 关系图，给可行性判断（PIVOT条件之一）。
- PaperKG = JSON盘 + 内存子图，对标 GraphRAG局部查询模式，不引 Neo4j、不用 LLM断关系（守 evidence则）。
-法见 AutoResearchClaw对标 §14，这里只引用不重述。


## 4. RAG 评估闭环（板 #3，闭环）

把现在「只有 baseline中率」补成四个标准指标：

|标 | 定义 |么算 |
|---|---|---|
| Recall@K | top-K 里命中 gold 的比例 | 造 gold set（已知相关论文），跑 pipeline算 |
| MRR | 第一条命中 gold 的倒数排名 | 同上 |
| Citation Coverage |告里每条论断是否有 EvidenceRef |查 proposal draft每条 claim是否有 evidence_id |
| Evidence Precision | evidence中 gold 的比例 | gold set对照 |

工具对标：Ragas（RAGAS） / DeepEval /自建。口径「我没引 Ragas（MVP不加重依赖），自建四个指标，对标 Ragas 的 faithfulness/context_precision」。

Eval闭环的面试加分点：能讲「离线 eval集 +在线 A/B + LLM-as-judge种」，其中 LLM-as-judge守「LLM 只判定相关性，不入 supports」（与多层验证链一致）。

## 5. 多层引用验证链（接 §3.2，把单层 URL Verified扩展成四层）

| Layer |什么 |来判 |
|---|---|---|y LLM |
| L1 可链接性 | URL HTTP 200，metadata整（title/authors/year） |序 |
| L2 来源权威性 | 发表在 peer-reviewed venue / arXiv 有 DOI |则 +启发式 |
| L3 元数据完整性 | references / dataset字段非空 |序 |
| L4 内容相关性 | query vs abstract 相关 | LLM，但只生成 verification_report，不入 supports |

不变式守：LLM 只判 L4，不写 evidence。产 `verification_report.json`，对标 Great Expectations / dbt tests / OpenLineage。

## 6.阶段演进路线（design-only，规模可调）

|段 | 产出 | 口径升档 | 估工作量 |
|---|---|---|---|
|段 A | Modular RAG + BM25+RRF合 + 自建 4标 eval | lightweight →近 implemented | 1-2 天 |
|段 B | CrossEncoder Rerank bge-reranker | lightweight | 0.5 天 |
|段 C | Qdrant适配层（FAISS占位） | design-only | 0.5 天 |
|段 D | 多层验证链 L1-L4 + verification_report.json | lightweight | 1 天 |
|段 E | PaperKG 1-hop邻域 query + LinkwiseContext | design-only | 1-1.5 天 |

每阶段最小可测单元 = 实现 + 1-2 个 pytest，全绿才能升档（守 CLAUDE.md 不变式）。

## 7.试讲法树（面试官追问到哪一档，答到哪一档）

-（够过）：「RAG 不是简单向量库，是 QueryPlanner + Retriever + Reranker + Verifier + Reporter段管线，对标 Haystack Pipeline」。
- 中（加分）：「Hybrid Search BM25+Dense 用 RRF，Reranker CrossEncoder top-K，Eval 四指标 Recall@K/MRR/Citation Coverage/Evidence Precision」。
- 深（最优解方向）：「多层验证链 L1-L4 + PaperKG关系图 + 显式熔断；LLM 只判相关性不写 evidence；provider离不锁死 Qdrant/FAISS」。

讲完一句收尾：「我把扩展位都留了接口和 design-only文档，没为了面试短期好看把项目做重」。

## 8. 与 CLAUDE.md 不变式对齐

- 设计不冒充已落地：全文 design-only，落地以代码 + pytest为准。
- LLM 不直接写 evidence：L4 只生成 verification_report，不入 supports。
- pytest总数只增不减：本稿无代码，无 pytest义务。
- 不引未列依赖：Qdrant/Chroma/Ragas/bge只作 design-only对标，未加入 pyproject.toml。
- LLM路径配 heuristic fallback：BM25/RRF/CrossEncoder都有纯 Python fallback。

## 9. 与既有文档交叉引用

- `docs/interview/AutoResearchClaw_对标与小型化移植.md` §3.2（多层验证链）/ §3.3（熔断）/ §14（多论文 RAG + PaperKG）
- `docs/interview/RAG_Design_Explainer.md`（当前 lightweight法）
- `docs/interview/Deep_Dive_QA_RAG.md`（深挖 Q&A）
- `docs/interview/Technical_Highlights.md`（三档口径）

