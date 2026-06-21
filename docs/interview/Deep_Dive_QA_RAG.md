# Deep Dive Q&A — RAG 检索增强生成（Session 38 补充）

> 面试时被连续追问 RAG 细节时，怎么稳定输出？

---

## Q1: 什么是 RAG？为什么你的项目需要？

**短答：** RAG = Retrieval-Augmented Generation，先检索再生成。在 PaperAgent 中用于把题目相关的论文/数据集候选喂给 LLM，减少幻觉。

**深答：**
- 直接让 LLM 推荐论文 → 95% 是编的（hallucination）
- 真实检索出的论文 → LLM 基于真实标题/摘要评分
- 这不是「搜索 + 摘要」，而是「搜索 + 结构化抽取 + 评分 + 解释」

**项目证据：**
- `apps/api/app/services/rag_pipeline.py` — 6 步 pipeline
- `docs/interview/RAG_Design_Explainer.md`

---

## Q2: 你的检索用了什么算法？

**短答：** Hybrid (Sparse + Dense) + RRF 融合 + 5 因子 Rerank。

**深答：**
- **Sparse (BM25)**: 关键词匹配，OOV 鲁棒
- **Dense (Embedding)**: 语义匹配
- **RRF (Reciprocal Rank Fusion)**: Cormack 2009，两个 ranked list 融合
  ```
  rrf_score(d) = sum(1 / (k + rank_i(d)))  # k=60
  ```
- **5 因子 Rerank**: 关键词覆盖、年份、引用、类型、来源

**项目证据：**
- `apps/api/app/services/rag_pipeline.py:60` — RRF 实现
- `apps/api/app/services/rag_pipeline.py:120` — Rerank

---

## Q3: 评估怎么做？

**短答：** 8 个指标 + 5 个 failure detector。

**8 指标：**
1. nDCG@10 — 排序质量
2. MRR — 首个相关位置
3. Recall@K — 召回率
4. Precision@K — 准确率
5. Coverage — 主题覆盖
6. Diversity — 多样性
7. Latency — 延迟
8. Cost — 成本

**5 failure detector：**
- empty_retrieval
- low_recall
- hallucinated_url
- duplicate_top_k
- off_topic

**项目证据：**
- `apps/api/app/services/rag_evaluator.py` — 8 + 5
- `apps/api/tests/test_session34_rag_pipeline_eval.py` — 25 tests

---

## Q4: RAG 的边界是什么？

**诚实回答：**
- Mock embedding（真实环境需 sentence-transformers）
- 没有向量数据库（in-memory 倒排索引）
- 没有 rerank 模型（5 因子启发式）

**未来：**
- 接入真 Embedding API
- 接入 FAISS / Milvus
- 接 ColBERT / BGE-reranker

---

## Q5: 怎么防幻觉？

3 层防护：
1. **检索约束** — LLM 只能引用真实候选
2. **URL 验证** — 候选必须 URL 可访问
3. **Gate 校验** — 不可写的 agent 拒绝

```
LLM 生成 → 候选列表
        ↓
URL Verified?
   ↓ yes      ↓ no
Evidence    Candidate
        ↓
Ready for export
```

---

## Q6: Hybrid 为什么比单一好？

**短答：** 关键词召回强（OOV 鲁棒），语义召回召回高，二者互补。

**深答：**
- Sparse 优势：精确术语、年份、作者名
- Sparse 劣势：同义词、跨语言
- Dense 优势：语义、改写
- Dense 劣势：精确术语、OOV

RRF 比 `score = 0.5*sparse + 0.5*dense` 更好，因为：
- 不需要 score 校准
- 单一 rank list 足够
- 实战验证（Cormack 2009, BEIR benchmark）

---

## Q7: 怎么判断检索结果好不好？

**不是** 单纯看 Recall@K。

应该是：
- `nDCG@10` — 排序质量（高排名的对更重要）
- `MRR` — 用户点击第一个的概率
- `Coverage` — 是否覆盖主题
- `Diversity` — 是否同质化

**面试回答模板：**

> 「我们不只看 Recall@K，因为 PaperAgent 关注的是**前 10 个候选**。如果前 10 个都好但 100-1000 不好，Recall@1000 也会低，但用户体验好。所以用 nDCG@10 + MRR + Coverage 组合看。」

---

## Q8: RAG 和微调什么场景用哪个？

| 场景 | RAG | 微调 |
|---|---|---|
| 知识更新频繁 | ✅ | ❌ |
| 需要引用出处 | ✅ | ❌ |
| 输出风格定制 | ❌ | ✅ |
| 任务特定推理 | ❌ | ✅ |
| 成本敏感 | ✅ | ❌ |

**PaperAgent 用 RAG：** 论文推荐需要出处 + 知识更新频繁。

---

## Q9: 你的 embedding 怎么来的？

**诚实回答：** Mock embedding（hash + noise）。

真实环境：
- `sentence-transformers/all-MiniLM-L6-v2` (轻量)
- `BAAI/bge-large-en-v1.5` (高质量)
- 或 OpenAI `text-embedding-3-small`

**为什么 mock？** 离线可测、不依赖 API key、可解释。

---

## Q10: 如果检索为空怎么办？

3 层降级：
1. **empty_retrieval** — 检测器触发
2. **触发扩展** — 拆解更多关键词（Method → Method+Dataset）
3. **LLM 兜底** — 让 LLM 推荐 5 个关键词再查

**关键不变量：** 检索失败不暴露给用户，由 fallback 接管。

---

## Q11: RAG 的延迟怎么优化？

**当前：** 200-500ms（mock 检索 + 启发式 rerank）

**未来优化：**
- Embedding cache
- 向量库 ANN（FAISS HNSW）
- 异步并行（Sparse + Dense 并发）
- 预计算（query → cached results）

---

## Q12: 多语言怎么处理？

**当前：** 主要中文，BM25 tokenizer 对中文友好（ik/jieba）。

**深答：**
- 跨语言检索：mContriever / mE5
- Query 翻译：中文 → 英文
- 候选排序：跨语言 embedding 空间

**诚实回答：** PaperAgent 当前没做跨语言，主要中文 + 部分英文论文。

---

## Q13: RAG 的最大陷阱是什么？

**回答：** 「幻觉 URL」 — LLM 引用真实标题但**编造 URL**。

**PaperAgent 解法：**
- `URLVerified` 状态必须 HTTP HEAD 200
- 不可访问直接降级为 Candidate
- 永不晋升为 Evidence

---

## Q14: 你怎么和 LangChain RAG 区别？

| 维度 | LangChain RAG | PaperAgent RAG |
|---|---|---|
| Pipeline | 链式调用 | 6 步显式 pipeline |
| 评估 | 需手写 | 内置 8 指标 + 5 检测器 |
| Gate | 无 | Hybrid 检索 + URL 验证 + Gate |
| 审计 | 需手写 | Trace 全程 |
| 失败处理 | 抛异常 | 降级 + failure detector |

---

## Q15: 多模态 RAG 怎么做？

**当前：** 仅文本（标题 + 摘要）。

**未来：**
- 论文图表解析（PDFFigures2）
- 公式识别
- 表格检索

**项目证据：** `docs/interview/RAG_Design_Explainer.md` §未来扩展

---

> **面试重点：** PaperAgent RAG 不是「接了个 LangChain」，而是「把每一步都做成可测、可评、可降级的显式 pipeline」。评估不是花架子，failure detector 是产品稳定性的关键。
