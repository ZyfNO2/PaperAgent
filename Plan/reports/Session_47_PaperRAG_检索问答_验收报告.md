# Session 47 验收报告 — Paper RAG 检索与问答

## 1. 范围

在 Session 46 个人论文库（S46）基础上，接上**真实全文 chunk 级 RAG**：
- chunk embedding（in-memory，无外部向量库）
- 索引落盘 + 加载 + 幂等
- query rewrite + keyword + dense + RRF 融合
- chunk 级 5 因子 reranker
- LLM 问答 + EvidenceRef 回溯 + fallback
- `/ask` + `/{paper_id}/index` 2 端点
- 入库自动索引联动

## 2. 新增产物

### 2.1 Schema（`app/schemas_paper_rag.py`）

| 模型 | 字段 |
|---|---|
| `EvidenceRef` | `paper_id`, `chunk_id`, `page_start?`, `page_end?`, `quote`, `support_type` (direct/indirect/background/contradiction), `score` |
| `PaperRAGAnswer` | `question`, `answer`, `evidence_refs[]`, `unsupported_claims[]`, `confidence`, `used_papers[]`, `retrieval_mode` (llm/fallback) |
| `PaperRAGAskRequest` | `question`, `scope` (all_papers/accepted_papers/specific), `paper_ids?`, `top_k` |
| `PaperIndexRequest` / `PaperIndexResponse` | `force`, `chunk_count`, `indexed`, `skipped`, `duration_ms` |

### 2.2 service 模块（`app/services/paper_library/`）

| 文件 | 职责 |
|---|---|
| `embedding.py` | mock bag-of-words (top-N=256) + cosine + provider switch |
| `indexer.py` | `build_index` / `load_index` / `reset_index` |
| `retriever.py` | `rewrite_query` (中英) + `keyword_retrieve` + `dense_retrieve` + `rrf_fuse` + `retrieve` + scope 过滤 |
| `reranker.py` | `rerank_chunks` 5 因子加权 |
| `paper_qa.py` | `build_context` + `answer_with_llm` + `fallback_answer` + `compute_confidence` |
| `__init__.py` | S46 ingest 末尾自动调 `indexer.build_index` (best-effort) |

### 2.3 API（`app/api/v1/paper_library.py`）

新增 2 端点（与 S46 4 端点合并到同一 router）：

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/v1/projects/{project_id}/paper-library/{paper_id}/index` | `{force?: bool}` | `PaperIndexResponse` |
| POST | `/api/v1/projects/{project_id}/paper-library/ask` | `PaperRAGAskRequest` | `PaperRAGAnswer` |

### 2.4 索引落盘结构

```text
.runtime/paper_library/{project_id}/index/
├── manifest.json          # S46 已有
├── embeddings.jsonl       # 每行: {chunk_id, paper_id, vector: [...]}
└── chunks_index.json      # chunk_id → {paper_id, section, text, chunk_type, page}
```

## 3. Embedding 策略

```text
Mock (默认, EMBEDDING_PROVIDER=mock):
  - vocab = corpus top-256 高频 token (英文+中文)
  - 向量 = token 频次向量
  - deterministic & testable

真实 API (预留开关):
  - EMBEDDING_PROVIDER env (openai / huggingface)
  - 当前未配置时强制 mock
  - 仅留接口, 本轮不实现真实调用
```

## 4. 检索流程图

```text
用户问题
    ↓
rewrite_query (中英对齐 + 2-gram)
    ↓
[scope filter: all/accepted/specific] → chunks_index 过滤
    ↓
keyword_retrieve (Jaccard-like overlap)
  + dense_retrieve (cosine on embeddings)
    ↓
rrf_fuse (k=60)
    ↓
rerank_chunks (5 因子加权)
    ↓
top-k chunks
    ↓
build_context → LLM 问答
    ↓
PaperRAGAnswer (evidence_refs + unsupported_claims + confidence)
```

LLM 失败 → fallback (retrieval_mode="fallback", confidence=0)

## 5. Reranker 5 因子

| 因子 | 权重 | 说明 |
|---|---|---|
| keyword_match | 0.35 | query token 在 chunk 的命中比例 |
| section_type | 0.25 | method/experiment > result > abstract > introduction > reference |
| recency | 0.15 | paper year 越近越高 |
| rerank_score | 0.15 | RRF fused score 归一化 |
| type_coverage | 0.10 | 少数类型 chunk 加分 |

## 6. 与 S34 rag_pipeline 的区别

| 维度 | S34 rag_pipeline | S47 paper_rag |
|---|---|---|
| 作用对象 | 候选元数据 (title+abstract) | 全文 chunk (in-context) |
| dense 实现 | title+abstract token overlap | 真词袋向量 + cosine |
| rerank 因子 | 5 因子含 url_verified | 5 因子含 section_type |
| 输出 | RetrievalCandidate[] | PaperRAGAnswer + EvidenceRef |
| 真实入库 | 否（演示级） | 是（S46 论文库） |

两者并存：S34 保留作面试演示「Hybrid RAG 流程」；S47 是真实可用的论文库 RAG。

## 7. 测试

| 类别 | 用例数 | 关键覆盖 |
|---|---|---|
| Embedding | 6 | 确定性 / cosine / corpus shape |
| Indexer | 4 | 构建 / 幂等 / force / 指定 paper |
| Retriever | 6 | rewrite 中英 / RRF / sparse+dense / scope |
| Reranker | 3 | section_type (method>reference) / recency |
| PaperQA | 7 | build_context / fallback / LLM 带 ref / unsupported / 异常 / 无命中 |
| Scope filter | 2 | specific / accepted_papers |
| API 端点 | 6 | index/ask 形状 / no-hit / mock LLM / fallback / 422 |
| Ingest-index 联动 | 2 | upload auto-index / arxiv auto-index |
| Schemas | 2 | serialize |
| **总计** | **38 新增** | |

**pytest 结果：**
- S47 文件: 38/38 通过
- 全量: 675 通过 / 1 skip (基线 612 → +63)
- 无回归

## 8. Design-only 边界

- 不接 FAISS/Chroma/pgvector（本轮 in-memory）
- 不接真实 embedding API（仅留接口，默认 mock）
- 不做 claim grounding 写回 FinalPackage（S48）
- 不做 SmallPaperCard / 章节映射（S49）
- 不做 RAG 评估回归基线（S50）
- 不动 S34 rag_pipeline
- 不动 CLAUDE.md

## 9. 面试讲法

> S34 是我最早做的 Hybrid RAG 流程演示，操作元数据级候选；S47 把同一套 sparse+dense+RRF+rerank 落到 S46 真实论文库的全文 chunk 上，新增 chunk 级 5 因子 reranker、EvidenceRef 回溯、LLM fallback。三层串起来就是：S15 选材 → S46 入库 → S47 检索问答。

## 10. 已知约束 / 后续

- 当前 embedding 是 mock 词袋，跨文档语义召回弱；下一轮可切真实 API
- scope="accepted_papers" 通过 arxiv_id 关联 evidence ledger 与 paper_library；paper_id ↔ arxiv_id 映射靠 manifest
- 索引文件未做并发锁；并发 ingest 可能 race（接 S48 时考虑加锁）
- 无 LLM 调用成本统计（prompt tokens 估算未做）

## 11. 产物清单

新增 / 修改文件：
- `apps/api/app/schemas_paper_rag.py` (new)
- `apps/api/app/services/paper_library/embedding.py` (new)
- `apps/api/app/services/paper_library/indexer.py` (new)
- `apps/api/app/services/paper_library/retriever.py` (new)
- `apps/api/app/services/paper_library/reranker.py` (new)
- `apps/api/app/services/paper_library/paper_qa.py` (new)
- `apps/api/app/services/paper_library/__init__.py` (modified — auto-index after ingest)
- `apps/api/app/api/v1/paper_library.py` (modified — add 2 endpoints)
- `apps/api/tests/test_session47_paper_rag.py` (new, 38 tests)

无修改：
- `apps/api/app/main.py`（router 已挂载）
- `apps/api/app/services/rag_pipeline.py`（S34 保留）
- `CLAUDE.md`