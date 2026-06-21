# RAG 面试设计讲解（Session 34）

> 一份专门给面试官讲解的 RAG 设计稿。
> 不只是「我们用了 RAG」，而是「我们的 RAG 是这样分层的」。

---

## 1. 一句话定位

PaperAgent 的 RAG 是 **多层混合检索 + 评估驱动** 的科研证据检索流程：QueryPlan → Sparse/Dense Hybrid → RRF Fusion → 多因子 Rerank → CandidateResource → RagEvalReport。

---

## 2. 为什么不是简单向量库？

| 简单向量库 | PaperAgent RAG |
|---|---|
| 把全部候选塞进 embedding | 三类证据（论文 / 数据集 / 仓库）独立召回 |
| 不去重 / 难去重 | 多 key 归一化（DOI / arxiv_id / OpenAlex ID）+ 标题 Jaccard |
| 召回后直接用 | 召回 → 融合 → 重排 → 评估 → 导入 |
| 没有评估 | Recall@K / MRR / Citation Coverage / Evidence Precision |

**关键差异：** 我们不假设 embedding 能解决一切 — 学术文献存在大量别名、版本、跨源重复，单向量召回在 baseline 召回上漏检率高。

---

## 3. Pipeline 详细

```
QueryPlan (paper_queries / dataset_queries / repo_queries)
   ↓
[1] Sparse Retriever (mock BM25) — 关键词 Jaccard overlap
   ↓
[2] Dense Retriever (mock embedding) — 语义 proxy（title+abstract token overlap × year weight）
   ↓
[3] RRF Fusion — Reciprocal Rank Fusion (Cormack 2009)
   score = Σ 1 / (k + rank)   k=60
   ↓
[4] Reranker — 5 因子加权
   w_keyword_match (0.35) + w_url_verified (0.20)
   + w_reproducibility (0.25) + w_type_coverage (0.10) + w_recency (0.10)
   ↓ URL 未验证 * 0.4 惩罚
[5] top_k_final = 10
   ↓
[6] RagEvalReport
```

---

## 4. 五因子 Rerank 设计

| 因子 | 权重 | 解释 |
|---|---|---|
| **keyword_match** | 0.35 | 关键词与 title/abstract 的 Jaccard overlap，1.0 = 全部命中 |
| **url_verified** | 0.20 | URL 通过 CDP/HTTP 验证的为 1.0，否则 0.4 |
| **reproducibility** | 0.25 | paper 有代码 + 数据 = 1.0；repo 有 license + readme = 1.0 |
| **type_coverage** | 0.10 | 少数类型加权，防止某类候选垄断 |
| **recency** | 0.10 | 年份越近分数越高（5% 折扣 / 年） |

**为什么需要多因子？**

- 单 rerank 因子会偏好某类信号，丢失其他信号
- URL verified 单独作为 rerank 因子，避免了「先选后验证」的反模式
- 复现信号独立于文本相似度 — 这是「开题」场景与「问答」场景的关键差异

---

## 5. RRF Fusion 为什么用 Reciprocal Rank 而不是加权平均？

加权平均需要先归一化分数（不同 retriever 的分数尺度不同），归一化又引入了额外参数。RRF 只用 **rank**，对单一 retriever 的尺度变化不敏感，更鲁棒。

```python
# Cormack 2009 RRF
score(doc) = Σ 1 / (k + rank_in_retriever)
k = 60 是经验值（无参数化时表现稳定）
```

**面试回答模板：**
> 「我们用 RRF 而不是加权融合，是因为稀疏和密集检索的分数尺度不一致，强行加权需要先归一化。RRF 只用 rank，避免了尺度问题，并且可以自然扩展到 N 个 retriever。」

---

## 6. 评估指标（5 个核心 + 3 个类型覆盖）

| 指标 | 公式 | 用途 |
|---|---|---|
| **Recall@K** | (前 K 中相关数) / (总相关数) | 召回质量 |
| **MRR** | 1 / 第一个相关候选的 rank | 首位命中率 |
| **Citation Coverage** | (绑定 evidence 的章节) / (总章节) | 报告完整度 |
| **Evidence Precision** | (引用的 accepted/core) / (引用总数) | 引用质量 |
| **URL Verified Rate** | (url_verified=True) / (总候选) | 外部可达性 |
| **Paper Coverage** | 1.0 if paper in candidates else 0.0 | 类型完整性 |
| **Dataset Coverage** | 同上 | 同上 |
| **Repo Coverage** | 同上 | 同上 |

**Failure Cases 自动检测：**

1. `no_dataset` — 检索不到数据集
2. `no_repo` — 检索不到代码仓库
3. `url_unverified` — >50% 候选 URL 未验证
4. `low_relevance` — >50% 候选 rerank < 0.3
5. `type_imbalance` — 某类型占比 >85%

---

## 7. 失败降级

```
LLM 失败        → heuristic keyword decomposition
向量库不可用    → mock dense (title overlap proxy)
sparse 为空     → RRF 自动用 dense 分数
dense 为空     → RRF 自动用 sparse 分数
两者都空       → 返回 partial + failure_case
URL 验证失败   → rerank score * 0.4 惩罚
```

---

## 8. 面试常见追问

### Q1: RRF 和 Reciprocal Rank 的区别？

RR (Reciprocal Rank) = 1 / rank（单个 retriever）。
RRF = 多个 retriever 的 RR 求和（多 retriever 融合）。

### Q2: 为什么不直接训练一个 cross-encoder rerank？

- 训练成本：开题场景的 relevance 定义因校而异，标注成本高
- 推理成本：cross-encoder 比双塔慢 100×
- 替代方案：多因子加权可解释 + 可调，面试时能讲清楚每个因子的来源

### Q3: 怎么验证 RAG 真的在 work？

- 离线评估：ground truth set (人工标注的相关候选) → Recall@K
- 在线评估：用户选中的 imported candidates / 总 candidates (candidate_to_evidence_rate)
- 失败案例：no_dataset / no_repo 是结构化失败指标

### Q4: RAG 找错了怎么办？

三层防护：
1. rerank 时 URL 未验证 * 0.4 惩罚
2. Rerank 分数 < 0.3 自动归入 failure_case
3. 用户最后 manual gate 决定是否 import

### Q5: 跟 LangChain/LlamaIndex 有什么差异？

我们 **不** 用 LangChain/LlamaIndex 作为顶层框架：
- LangChain 的 chain 抽象对学术检索场景 over-engineering
- 我们只用了 LangChain 风格的 PromptTemplate，但不引入 callback / memory
- 评估指标是我们自己的（Citation Coverage / Evidence Precision 是开题场景特有）

---

## 9. 可展示文件清单

面试时可以让面试官点开：

- `apps/api/app/schemas_rag_eval.py` — 数据模型（RagPipelineConfig 5 因子可调）
- `apps/api/app/services/rag_pipeline.py` — Pipeline 入口
- `apps/api/app/services/rag_evaluator.py` — 评估入口
- `apps/api/tests/test_session34_rag_pipeline_eval.py` — 25 个测试覆盖
- `docs/interview/Interview_QA_Cards.md` — 30 张 QA 卡里有 5 张 RAG 类

---

## 10. 未来扩展

- 接真实向量库（Pinecone / Weaviate）
- 训练 cross-encoder rerank
- 用户反馈闭环（用户标记的「不相关」回流到 ground truth）
- 跨 project 共享 ground truth
- A/B 测试不同 RRF k 值

---

> **面试重点强调：** PaperAgent 的 RAG 不是「用了一个向量库」，而是「分 QueryPlan → Hybrid → Rerank → Eval 四层，每层都有可测合同和可解释的指标」。